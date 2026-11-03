"""Painel Windows Tkinter. O domínio e banco de dados podem ser testados sem GUI."""
from __future__ import annotations
from dataclasses import replace
import json
import os
from pathlib import Path
from queue import Queue, Empty
from tkinter import Tk, Toplevel, Frame, Label, Button, Entry, StringVar, IntVar, Checkbutton, Canvas, filedialog, messagebox, Text, END
from tkinter import ttk
from time import strftime, localtime, time
from .domain import FlightTracker, Career, MISSIONS, AIRPORTS, distance_nm, Phase
from .storage import Storage
from .sim_adapter import SimConnectWorker
from .demo import demo_samples
from .neo_inspect import inspect_neofly, discover_neofly_databases
from .pilot import QUALIFICATIONS, qualification_eligibility, flight_xp, level_progress, progress_fraction
from .contracts import (AirportCatalog, TYPES, TYPE_BY_CODE, PLANE_BY_CODE,
                        generate_offers, eligibility, matches_aircraft)
from .employment import (EMPLOYER_BY_CODE, vacancies, weekly_period,
    employment_eligibility, generate_employer_routes, OWN_MIN_LEVEL, OWN_INVESTMENT)
from .flightplan import export_vfr_plan
from .finance import AIRCRAFT_ECONOMY, brl, estimated_minutes
from .contracts import aircraft_model
from .fuel import FuelManager
from .fleet import used_market, resale_price
from .planning import Preflight, inspect_preflight, aircraft_title_matches
from .aircraft_catalog import scan_installed_aircraft, detect_package_roots
from .ingame_bridge import PanelState, LocalPanelServer
from . import __version__

BG = "#08111c"
PANEL = "#101e2d"
PANEL2 = "#172a3a"
FG = "#e4edf5"
MUTED = "#94a8bb"
CYAN = "#54c8d5"
GOLD = "#d4ae6e"
GREEN = "#63cc99"
RED = "#e58b8b"
FONT = "Segoe UI"


def state_dir():
    base = Path(os.getenv("APPDATA") or Path.home() / ".local" / "share")
    return base / "AeroCarreira-Lab"


class Application:
    def __init__(self):
        self.root = Tk()
        self.root.title("AeroCarreira • Flight Lab | " + __version__)
        self.root.geometry("1100x720")
        self.root.minsize(900, 640)
        self.root.configure(bg=BG)
        self.queue = Queue()
        self.session_generation = 0
        self.sim = None
        self.tracker = FlightTracker()
        self.storage = Storage(state_dir() / "carreira.db")
        self.location_recovered=self.storage.recover_legacy_location()
        self.fuel_manager=FuelManager(self.storage)
        self.fuel_penalty_frozen=0.0
        self.fuel_ref_frozen=None
        self.fuel_mode_at_takeoff=False
        self.fuel_warning_at=0.0
        self.fuel_company_guard=None
        self.career = Career(int(self.storage.get_setting("balance") or 0))
        self.recovered = False
        self.restore_error = None
        self.realism_frozen = 0.0
        self.realism_mission = None
        try:
            checkpoint = self.storage.get_checkpoint()
            if checkpoint:
                self.career.restore(checkpoint.get("career", {}))
                self.tracker = FlightTracker.from_snapshot(checkpoint["tracker"])
                if self.tracker.phase == Phase.AIRBORNE and self.career.mission:
                    self.realism_frozen = float(checkpoint.get('realism_frozen',0.0))
                    self.realism_mission = checkpoint.get('realism_mission')
                self.fuel_company_guard=checkpoint.get('fuel_company_guard')
                if self.tracker.phase == Phase.AIRBORNE:
                    self.fuel_penalty_frozen=float(checkpoint.get('fuel_penalty_frozen',0.0))
                    self.fuel_mode_at_takeoff=bool(checkpoint.get('fuel_mode_at_takeoff',False))
                    self.fuel_ref_frozen=checkpoint.get('fuel_ref_frozen')
                self.recovered = self.tracker.phase == Phase.AIRBORNE or self.career.mission is not None
        except (KeyError, ValueError, TypeError) as exc:
            self.restore_error = str(exc)
        self.last_checkpoint_time = 0.0
        self.last_sample = None
        self.demo_seq = demo_samples()
        self.demo_index = 0
        self.connected = False
        self.mode = "Desconectado"
        self.balance_var = StringVar(value=brl(self.career.balance))
        self.status_var = StringVar(value="Sem conexão • Demo disponível")
        self.pilot_var = StringVar(value="PILOTO • não cadastrado")
        self.level_progress_var = StringVar(value="Cadastre seu piloto para acompanhar o nível")
        self.level_bar = None
        self.level_fraction = 0.0
        self.pilot_dialog = None
        self.market_dialog = None
        self.employment_dialog = None
        self.finance_dialog = None
        self.fleet_dialog = None
        self.planning_dialog = None
        self.airport_catalog = None
        self.bridge_state = PanelState()
        self.bridge = LocalPanelServer(self.bridge_state)
        self.bridge_error = None
        try: self.bridge.start()
        except OSError as exc: self.bridge_error = str(exc)
        self._refresh_pilot_summary()
        self.info_var = StringVar(value="Sem telemetria")
        self.phase_var = StringVar(value="AGUARDANDO")
        self.mission_var = StringVar(value="Nenhum contrato ativo")
        self.flight_vars = {k: StringVar(value="—") for k in ["ias", "gs", "agl", "alt", "vs", "lat", "lon", "fuel"]}
        self._build()
        if self.restore_error:
            self._log(f"ALERTA: checkpoint não restaurado: {self.restore_error}")
        if self.location_recovered:
            self._log('Localização do Cessna inicial recuperada do último pouso: '+self.location_recovered)
        if self.bridge_error:
            self._log(f'Painel local indisponível: {self.bridge_error}')
        else:
            self._log('Painel de bordo local: http://127.0.0.1:8769 (SDK ainda em testes)')
        if self.recovered:
            self._log("Estado de contrato/voo anterior recuperado. Conecte ao MSFS para continuar.")
            self.phase_var.set(self.tracker.phase.value.upper())
            self._show_mission()
        self.root.after(200, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def label(self, parent, text, size=10, color=FG, bold=False, bg=None):
        return Label(parent, text=text, bg=bg or parent.cget("bg"), fg=color,
                     font=(FONT, size, "bold" if bold else "normal"), anchor="w")

    def button(self, parent, text, cmd, accent=False, width=None):
        return Button(parent, text=text, command=cmd, width=width,
                      bg=CYAN if accent else PANEL2, fg=BG if accent else FG,
                      activebackground=GOLD if accent else "#294357",
                      activeforeground=BG if accent else FG,
                      relief="flat", bd=0, padx=13, pady=9,
                      font=(FONT, 10, "bold"), cursor="hand2")

    def _progress_meter(self, parent, fraction: float, width: int = 160,
                        height: int = 9, color: str = CYAN):
        """Barra Midnight sem tema do SO, redimensionável e sem valores fictícios."""
        meter = Canvas(parent, width=width, height=height, bg=PANEL2,
                       highlightthickness=0, bd=0, relief="flat")
        meter.fraction = progress_fraction(fraction, 1)
        meter.fill_color = color
        meter.bind("<Configure>", lambda _event: self._draw_meter(meter))
        return meter

    @staticmethod
    def _draw_meter(meter):
        if not meter.winfo_exists():
            return
        width = meter.winfo_width()
        height = meter.winfo_height()
        meter.delete("all")
        meter.create_rectangle(0, 0, width, height, fill="#284155", outline="")
        fill_width = round(width * meter.fraction)
        if fill_width > 0:
            meter.create_rectangle(0, 0, fill_width, height,
                                   fill=meter.fill_color, outline="")

    def _set_meter(self, meter, fraction: float):
        meter.fraction = progress_fraction(fraction, 1)
        self._draw_meter(meter)

    def section(self, parent, title):
        f = Frame(parent, bg=PANEL, padx=16, pady=12)
        self.label(f, title, 11, GOLD, True).pack(anchor="w", pady=(0,9))
        return f

    def _build(self):
        header = Frame(self.root, bg=BG, padx=22, pady=14)
        header.pack(fill="x")
        self.label(header, "AERO", 20, FG, True).pack(side="left")
        self.label(header, "CARREIRA", 20, CYAN, True).pack(side="left")
        self.label(header, "  LAB  /  " + __version__, 11, MUTED).pack(side="left")
        right = Frame(header, bg=BG)
        right.pack(side="right")
        self.label(right, "CAIXA DA CARREIRA", 9, MUTED, True).pack(anchor="e")
        Label(right, textvariable=self.balance_var, font=(FONT, 18, "bold"), fg=GREEN, bg=BG).pack(anchor="e")
        Label(right, textvariable=self.pilot_var, font=(FONT, 9), fg=CYAN, bg=BG).pack(anchor="e")
        Label(right, textvariable=self.level_progress_var, font=(FONT, 8), fg=MUTED,
              bg=BG).pack(anchor="e", pady=(3, 2))
        self.level_bar = self._progress_meter(right, self.level_fraction, width=180, height=9)
        self.level_bar.pack(fill="x", anchor="e")

        bar = Frame(self.root, bg=PANEL, padx=18, pady=10)
        bar.pack(fill="x", padx=20)
        self.button(bar, "Conectar MSFS", self._connect, accent=True).pack(side="left", padx=(0,8))
        self.button(bar, "Demo sem MSFS", self._demo_start).pack(side="left", padx=(0,8))
        self.button(bar, "Avançar demo", self._demo_next).pack(side="left", padx=(0,8))
        self.button(bar, "Desconectar", self._stop).pack(side="left", padx=(0,8))
        self.button(bar, "Salvar log", self._save_log).pack(side="left", padx=(0,8))
        self.button(bar, "Meu piloto / Habilitações", self._pilot_window, accent=True).pack(side="left", padx=(0,7))
        self.button(bar, "Finanças / Hangar", self._finance_window, accent=True).pack(side="left")
        # Segunda linha preserva botões e telemetria de conexão em 1100px,
        # sem cortar o acesso ao painel experimental em telas menores.
        subbar = Frame(self.root, bg=PANEL, padx=18, pady=3)
        subbar.pack(fill="x", padx=20)
        self.button(subbar, "Painel local (experimental)", self._open_local_panel).pack(side="left")
        Label(subbar, textvariable=self.status_var, bg=PANEL, fg=CYAN,
              font=(FONT, 9)).pack(side="right")

        main = Frame(self.root, bg=BG, padx=20, pady=9)
        main.pack(fill="both", expand=True)
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(1, weight=1)
        telemetry = self.section(main, "01  /  TELEMETRIA AO VIVO")
        telemetry.grid(row=0, column=0, sticky="nsew", padx=(0,10), pady=(0,12))
        cards = Frame(telemetry, bg=PANEL)
        cards.pack(fill="x")
        for i,(key,caption,unit) in enumerate([
            ("ias","VELOCIDADE IND.","kt"), ("gs","VEL. SOLO","kt"),
            ("agl","ALTURA AGL","ft"), ("alt","ALTITUDE MSL","ft"),
            ("vs","RAZÃO VERTICAL","ft/min"), ("lat","LATITUDE","°"),
            ("lon","LONGITUDE","°"), ("fuel","COMBUSTÍVEL","gal"),
        ]):
            cell = Frame(cards, bg=PANEL2, padx=12, pady=10)
            cell.grid(row=i//4, column=i%4, padx=4, pady=4, sticky="nsew")
            cards.grid_columnconfigure(i%4, weight=1)
            self.label(cell,caption,8,MUTED,True,bg=PANEL2).pack(anchor="w")
            Label(cell,textvariable=self.flight_vars[key],font=(FONT,17,"bold"),fg=FG,bg=PANEL2,anchor="w").pack(anchor="w")
            self.label(cell,unit,8,MUTED,bg=PANEL2).pack(anchor="w")
        bottom = Frame(telemetry,bg=PANEL,pady=9)
        bottom.pack(fill="x")
        Label(bottom,textvariable=self.phase_var,fg=GREEN,bg=PANEL,
              font=(FONT,12,"bold")).pack(side="left")
        self.label(bottom,"SimConnect em somente leitura",9,MUTED).pack(side="right")

        missions = self.section(main, "02  /  MISSÕES E CONTRATOS")
        missions.grid(row=0,column=1,sticky="nsew",pady=(0,12))
        self.button(missions,"Mercado regional / Freelancer",self._market_window,accent=True).pack(fill="x",pady=(0,7))
        self.label(missions,"CONTRATOS FIXOS DE TESTE (legados)",8,MUTED,True).pack(anchor="w")
        self.mission_select = ttk.Combobox(missions, state="readonly", width=38, values=[
            f"{m.origin} → {m.destination}  |  {brl(m.reward)}  | {m.title}" for m in MISSIONS])
        self.mission_select.current(0)
        self.mission_select.pack(fill="x",pady=6)
        self.button(missions,"Aceitar contrato",self._accept,accent=True).pack(fill="x",pady=5)
        Label(missions,textvariable=self.mission_var,bg=PANEL,fg=GOLD,
              font=(FONT,10),wraplength=320,justify="left").pack(anchor="w",pady=8)
        self.button(missions,"Cancelar contrato",self._cancel).pack(fill="x")
        self.button(missions,"Preparar voo / Despacho",self._planning_window,accent=True).pack(fill="x",pady=(7,0))
        self.button(missions,"Carregar plano VFR no MSFS",self._prepare_active_plan).pack(fill="x",pady=(7,0))
        self.button(missions,"Vagas e companhias",self._employment_window).pack(fill="x",pady=(7,0))

        logp = self.section(main, "03  /  REGISTRO DE VOO")
        logp.grid(row=1,column=0,sticky="nsew",padx=(0,10))
        self.log_text=Text(logp,bg=PANEL2,fg=FG,insertbackground=CYAN,
                           height=9,font=("Consolas",10),relief="flat",padx=12,pady=12,
                           wrap="word",state="disabled")
        self.log_text.pack(fill="both",expand=True)
        self._log("Bem-vindo. Inicie uma demonstração ou conecte ao MSFS 2020.")
        self._log("O saldo começa em R$ 5.000 em carreira NOVA. Nenhum dado NeoFly foi importado.")

        rightcol = Frame(main,bg=BG)
        rightcol.grid(row=1,column=1,sticky="nsew")
        neofly=self.section(rightcol,"04  /  NEOFLY — ANÁLISE SEGURA")
        neofly.pack(fill="x",pady=(0,12))
        self.label(neofly,"Usa cópia local. Exporta somente nomes de tabelas/colunas.",9,MUTED).pack(fill="x")
        self.button(neofly,"Analisar common.db / std.bin",self._analyze).pack(fill="x",pady=8)
        self.button(neofly,"Localizar arquivos NeoFly",self._locate_neofly).pack(fill="x",pady=(0,8))
        self.label(neofly,"Não faz importação de progresso nesta versão.",9,MUTED).pack(fill="x")
        history=self.section(rightcol,"05  /  DIÁRIO DE BORDO")
        history.pack(fill="both",expand=True)
        self.history_text=Text(history,bg=PANEL2,fg=MUTED,height=7,font=("Consolas",9),
                               relief="flat",padx=9,pady=7,state="disabled")
        self.history_text.pack(fill="both",expand=True)
        self._refresh_history()

        foot=Frame(self.root,bg=BG,padx=22,pady=7)
        foot.pack(fill="x")
        self.label(foot,"Modo experimental • sem uso em aviação real • NeoFly não afiliado",9,MUTED).pack(side="left")
        self.label(foot,"MSFS 2020 / Windows / Python",9,MUTED).pack(side="right")

    def _log(self,msg):
        self.log_text.configure(state="normal")
        self.log_text.insert(END,f"[{strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see(END)
        self.log_text.configure(state="disabled")

    def _refresh_history(self):
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0",END)
        rows=self.storage.list_flights()
        if not rows:
            self.history_text.insert(END,"Nenhum voo registrado ainda.\n")
        for id,start,end,touch,stalls,mission,reward in rows:
            self.history_text.insert(END,f"#{id:03}  {int((end-start)/60)} min  "
                f"{('%.0f' % touch) if touch is not None else '—'} ft/min\n"
                f"      {mission or 'Voo livre'}  +{brl(reward)} bruto  avisos estol: {stalls}\n")
        self.history_text.configure(state="disabled")

    def _refresh_pilot_summary(self):
        pilot = self.storage.get_pilot()
        if pilot is None:
            self.pilot_var.set("PILOTO • não cadastrado")
            self.level_progress_var.set("NÍVEL —")
            self.level_fraction = 0.0
        else:
            stats = self.storage.pilot_stats()
            progress = level_progress(stats["xp"])
            self.pilot_var.set(f"{pilot['callsign']} • NÍVEL {progress['level']}")
            self.level_fraction = progress["fraction"]
            if progress["next_level"] is None:
                self.level_progress_var.set("NÍVEL MÁXIMO ATINGIDO")
            else:
                self.level_progress_var.set(
                    f"NÍVEL {progress['next_level']} • faltam {round((1-progress['fraction']) * 100)}%")
        if self.level_bar is not None:
            self._set_meter(self.level_bar, self.level_fraction)

    def _pilot_window(self):
        if self.pilot_dialog is not None and self.pilot_dialog.winfo_exists():
            self.pilot_dialog.lift()
            self.pilot_dialog.focus_set()
            return
        window = Toplevel(self.root)
        self.pilot_dialog = window
        window.title("FlightSimCarreira • Piloto e habilitações (virtuais)")
        window.geometry("850x760")
        window.minsize(720, 550)
        window.configure(bg=BG)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, "pilot_dialog", None), window.destroy()))

        # Rolagem obrigatória: cinco habilitações x três requisitos não cabem
        # na janela anterior de 720 px. Canvas não interfere no painel principal.
        outer = Frame(window, bg=BG)
        outer.pack(fill="both", expand=True)
        scroll = Canvas(outer, bg=BG, highlightthickness=0, bd=0)
        scroll.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=scroll.yview)
        scrollbar.pack(side="right", fill="y")
        scroll.configure(yscrollcommand=scrollbar.set)
        content = Frame(scroll, bg=BG)
        content_id = scroll.create_window((0, 0), anchor="nw", window=content)
        content.bind("<Configure>", lambda _event: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda event: scroll.itemconfigure(content_id, width=event.width))
        window.bind("<MouseWheel>", lambda event: scroll.yview_scroll(-int(event.delta/120), "units"))
        window.bind("<Button-4>", lambda _event: scroll.yview_scroll(-3, "units"))
        window.bind("<Button-5>", lambda _event: scroll.yview_scroll(3, "units"))

        def redraw():
            offset = scroll.yview()[0]
            for widget in content.winfo_children():
                widget.destroy()
            panel = Frame(content, bg=BG, padx=22, pady=17)
            panel.pack(fill="both", expand=True)
            self.label(panel, "MEU PILOTO  /  BLOCO 01", 17, CYAN, True).pack(anchor="w")
            self.label(panel, "Habilitações virtuais do jogo; não substituem certificações reais.",
                       9, MUTED).pack(anchor="w", pady=(3, 12))
            pilot = self.storage.get_pilot()
            fields = Frame(panel, bg=PANEL, padx=14, pady=12)
            fields.pack(fill="x")
            vars_ = {}
            for i, (key, caption, default) in enumerate((
                ("name", "NOME DO PILOTO", ""),
                ("callsign", "INDICATIVO", "FS0001"),
                ("home_icao", "BASE ICAO", "SBRF"))):
                cell = Frame(fields, bg=PANEL)
                cell.grid(row=0, column=i, padx=6, sticky="ew")
                fields.grid_columnconfigure(i, weight=3 if key == "name" else 1)
                self.label(cell, caption, 8, MUTED, True).pack(anchor="w", pady=(0, 5))
                var = StringVar(value=pilot[key] if pilot else default)
                vars_[key] = var
                Entry(cell, textvariable=var, bg=PANEL2, fg=FG, insertbackground=CYAN,
                      relief="flat", font=(FONT, 11), highlightthickness=0).pack(fill="x", ipady=7)

            def save():
                try:
                    if self.storage.get_pilot() is None:
                        self.storage.create_pilot(vars_["name"].get(), vars_["callsign"].get(), vars_["home_icao"].get())
                        self._log("Piloto cadastrado. Habilitação virtual PPA inicial concedida.")
                    else:
                        self.storage.update_pilot(vars_["name"].get(), vars_["callsign"].get(), vars_["home_icao"].get())
                        self._log("Cadastro atualizado sem alterar histórico ou saldo.")
                except ValueError as exc:
                    messagebox.showwarning("Cadastro do piloto", str(exc), parent=window)
                    return
                self._refresh_pilot_summary()
                redraw()

            self.button(fields, "Salvar cadastro" if pilot else "Criar piloto", save, accent=True).grid(
                row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(12, 0))
            stats = self.storage.pilot_stats()
            statsframe = Frame(panel, bg=PANEL, padx=14, pady=12)
            statsframe.pack(fill="x", pady=(12, 8))
            stats_caption = (f"VOOS NO DIÁRIO: {stats['flights']}      "
                             f"HORAS: {stats['hours']:.1f}      "
                             f"XP: {stats['xp']}  •  NÍVEL {stats['level']}      "
                             f"HABILITAÇÕES: {len(stats['qualifications'])}")
            self.label(statsframe, stats_caption, 10, GREEN, True).pack(anchor="w")
            progress = level_progress(stats["xp"])
            next_level = progress["next_level"]
            level_label = (f"NÍVEL {progress['level']}  →  {next_level}  •  "
                           f"{round(progress['fraction'] * 100)}% concluído" if next_level
                           else "NÍVEL MÁXIMO ATINGIDO")
            self.label(statsframe, level_label, 9, MUTED).pack(anchor="w", pady=(7, 4))
            self._progress_meter(statsframe, progress["fraction"], height=9).pack(fill="x")

            self.label(panel, "TRILHA DE HABILITAÇÕES", 11, GOLD, True).pack(anchor="w", pady=(8, 7))
            for q in QUALIFICATIONS:
                item = Frame(panel, bg=PANEL2, padx=11, pady=10)
                item.pack(fill="x", pady=4)
                row = Frame(item, bg=PANEL2)
                row.pack(fill="x")
                is_owned = q.code in stats["qualifications"]
                eligible, reason = qualification_eligibility(
                    q.code, stats["qualifications"], stats["flights"], stats["xp"], stats["hours"])
                self.label(row, f"{q.code}  •  {q.title}", 10, GREEN if is_owned else FG,
                           True, PANEL2).pack(side="left")
                if eligible and pilot is not None:
                    def grant(code=q.code):
                        try:
                            if self.storage.earn_qualification(code):
                                self._log(f"HABILITAÇÃO VIRTUAL CONCLUÍDA: {code}")
                                self._refresh_pilot_summary()
                                redraw()
                        except ValueError as exc:
                            messagebox.showwarning("Habilitação", str(exc), parent=window)
                    self.button(row, "Concluir etapa", grant, accent=True).pack(side="right")
                else:
                    missing = [pre for pre in q.prerequisites if pre not in stats["qualifications"]]
                    status = "OBTIDA" if is_owned else ("PRÉ-REQ.: " + ", ".join(missing) if missing else "EM PROGRESSO")
                    self.label(row, status, 8, GREEN if is_owned else MUTED,
                               bg=PANEL2).pack(side="right")
                self.label(item, q.description, 9, MUTED, bg=PANEL2).pack(anchor="w", pady=(3, 9))

                metrics = Frame(item, bg=PANEL2)
                metrics.pack(fill="x")
                for idx, (title, actual, target, display) in enumerate((
                    ("HORAS DE VOO", stats["hours"], q.hours,
                     f"{stats['hours']:.1f} / {q.hours:g} h"),
                    ("QUANTIDADE DE VOOS", stats["flights"], q.flights,
                     f"{stats['flights']} / {q.flights}"),
                    ("EXPERIÊNCIA (XP)", stats["xp"], q.xp,
                     f"{stats['xp']} / {q.xp}"),
                )):
                    col = Frame(metrics, bg=PANEL2)
                    col.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 8, 0))
                    metrics.grid_columnconfigure(idx, weight=1, uniform="metric")
                    self.label(col, title, 8, MUTED, True, bg=PANEL2).pack(anchor="w")
                    self.label(col, display if target > 0 else "Sem exigência", 9,
                               GREEN if target <= 0 or actual >= target else FG,
                               bg=PANEL2).pack(anchor="w", pady=(3, 4))
                    frac = progress_fraction(actual, target)
                    self._progress_meter(col, frac, height=8,
                                         color=GREEN if frac >= 1 else CYAN).pack(fill="x")
            self.label(panel, "XP: 25 por voo registrado + 15 por contrato concluído. "
                       "Voos antigos contam para horas e voos, sem XP retroativo.",
                       9, MUTED).pack(anchor="w", pady=(12, 4))
            self.label(panel, "Requisitos provisórios do jogo. Habilitações já obtidas são preservadas "
                       "mesmo após ajustar as metas.", 9, MUTED).pack(anchor="w")
            panel.update_idletasks()
            scroll.configure(scrollregion=scroll.bbox("all"))
            scroll.yview_moveto(offset)
        redraw()

    def _connect(self):
        # Reconectar NUNCA apaga a fase aérea ou a missão.
        was_demo = self.mode == "Demo"
        self._stop()
        if was_demo:
            self.tracker.reset()
        self.session_generation += 1
        self.sim = SimConnectWorker(self.queue, generation=self.session_generation)
        self.mode="MSFS"
        self.status_var.set("Conectando ao MSFS...")
        self._log("Iniciando monitoramento com reconexão automática.")
        self.sim.start()

    def _stop(self):
        if self.sim:
            self.sim.stop()
            self.sim = None
        self.session_generation += 1  # descartar mensagens de sessões antigas
        self.connected=False
        self.mode="Desconectado"
        self.status_var.set("Desconectado")

    def _demo_start(self):
        if self.career.mission or self.tracker.phase == Phase.AIRBORNE:
            self._log("Demo bloqueada: há um contrato/voo real pendente. Preserve-o ou cancele o contrato primeiro.")
            return
        self._stop()
        self.tracker.reset()
        self.demo_seq=demo_samples()
        self.demo_index=0
        self.mode="Demo"
        self.status_var.set("DEMONSTRAÇÃO • dados simulados")
        self._log("Demo iniciada. Aceite contrato SBRF → SIPE e avance as fases.")
        self._demo_next()

    def _demo_next(self):
        if self.mode!="Demo":
            self._log("Clique primeiro em 'Demo sem MSFS'.")
            return
        if self.demo_index >= len(self.demo_seq):
            self._log("Fim da demo. Inicie outra para reiniciar o avião.")
            return
        sample=self.demo_seq[self.demo_index]
        self.demo_index+=1
        self._process_sample(sample)

    def _accept(self):
        if self.mode not in ("MSFS", "Demo") or self.last_sample is None:
            messagebox.showwarning("Contrato", "Conecte ao simulador e aguarde a primeira telemetria em solo.")
            return
        if self.mode == "MSFS" and (not self.connected or not self.last_sample.on_ground or time()-self.last_sample.timestamp > 10):
            messagebox.showwarning("Contrato", "Aceite o contrato no solo, com telemetria atualizada.")
            return
        m=MISSIONS[self.mission_select.current()]
        if self.mode=="Demo" and m.id!="REC-ITA":
            self._log("A demonstração fixa simula SBRF → SIPE. Selecione o primeiro contrato.")
            return
        self._accept_specific(m)

    def _accept_specific(self, m):
        # No menu do MSFS ainda não existe SimConnect; o jogador pode
        # reservar contrato na base do seu perfil e preparar o plano .PLN.
        offline = self.mode == "Desconectado"
        if not offline and (self.mode not in ("MSFS", "Demo") or self.last_sample is None):
            messagebox.showwarning("Contrato", "Conecte ao MSFS e aguarde telemetria em solo.")
            return False
        if offline:
            profile=self.storage.get_pilot()
            if profile is None or m.origin != profile['home_icao']:
                messagebox.showwarning('Mercado', 'No modo offline só é possível aceitar na base cadastral do piloto.')
                return False
        if self.mode == "Demo" and m.id != "REC-ITA":
            messagebox.showwarning("Demo", "A demo fixa simula somente SBRF → SIPE.")
            return False
        if self.mode == "MSFS" and (not self.connected or not self.last_sample.on_ground
                                   or time() - self.last_sample.timestamp > 10):
            messagebox.showwarning("Contrato", "Aceite no solo com telemetria atualizada.")
            return False
        if m.category != "legacy":
            if self.storage.get_pilot() is None:
                messagebox.showwarning("Contrato", "Cadastre seu piloto primeiro.")
                return False
            allowed, reason = eligibility(m, self.storage.pilot_stats(),
                                          self.storage.owned_qualifications(),
                                          self.storage.family_experience())
            if not allowed:
                messagebox.showwarning("Contrato bloqueado", reason)
                return False
            if m.company_code and (self.storage.employment_state()['mode']!='empregado' or
                                   self.storage.employment_state()['employer_code']!=m.company_code):
                messagebox.showwarning('Contrato', 'Trecho exclusivo da companhia empregadora.')
                return False
            if self.storage.contract_completed(m.id):
                messagebox.showwarning("Contrato", "Este contrato já foi concluído. Aguarde nova oferta.")
                return False
        try:
            self.career.accept(m, None if offline else self.last_sample)
            self.storage.set_setting('preflight_v1','')  # outro contrato exige novo despacho
            self._show_mission()
            self._checkpoint(force=True)
            self._log(f"Contrato aceito: {m.title} ({m.origin} → {m.destination}).")
            if m.freelance:
                plane = PLANE_BY_CODE[m.employer_plane]
                self._log(f"FREELANCER: avião fornecido pelo contratante: {plane.name}.")
                self._log("Selecione este modelo no MSFS antes de decolar; o addon NÃO muda o avião automaticamente.")
                if not offline and self.last_sample and not matches_aircraft(self.last_sample.aircraft_title, m.employer_plane):
                    messagebox.showinfo("Freelancer — aeronave do contratante",
                        f"Contrato aceito. Avião designado: {plane.name}\n\n"
                        "Antes de decolar, selecione essa aeronave no MSFS. "
                        "O SimConnect deve reconhecer o modelo para validar o pagamento.")
            self._log('Pode gerar e carregar o plano VFR pelo botão Preparar plano da missão.')
            return True
        except ValueError as exc:
            messagebox.showwarning("Contrato",str(exc))
            return False

    def _market_window(self):
        if self.market_dialog is not None and self.market_dialog.winfo_exists():
            self.market_dialog.lift()
            return
        if not self.storage.get_pilot():
            messagebox.showwarning("Mercado regional", "Crie seu perfil em 'Meu piloto / Habilitações'.")
            return
        if self.airport_catalog is None:
            self.airport_catalog = AirportCatalog()
        catalog = self.airport_catalog
        sample = self.last_sample
        center = catalog.nearest(sample.latitude, sample.longitude, 6) if sample else None
        if center is None:
            home = self.storage.get_pilot()["home_icao"]
            center = catalog.locations.get(home)
        if center is None:
            messagebox.showwarning("Mercado regional", "Não foi possível localizar aeroportos próximos. "
                "Conecte o MSFS ou configure uma base ICAO presente no catálogo.")
            return
        window = Toplevel(self.root)
        self.market_dialog = window
        window.title("FlightSimCarreira • Mercado regional e Freelancer")
        window.geometry("1060x680")
        window.minsize(870,560)
        window.configure(bg=BG)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", lambda: (setattr(self,"market_dialog",None), window.destroy()))
        wrapper = Frame(window, bg=BG, padx=20, pady=16)
        wrapper.pack(fill="both",expand=True)
        self.label(wrapper, f"MERCADO REGIONAL  /  {center.icao} • {center.name}", 16, CYAN, True).pack(anchor="w")
        notes = ("Catálogo mundial disponível • apenas ofertas próximas são mantidas"
                 if catalog.global_catalog else
                 "Catálogo básico local: instale airportsdata para aeroportos do mundo inteiro")
        self.label(wrapper,notes,9,MUTED).pack(anchor="w",pady=(4,10))
        stats = self.storage.pilot_stats()
        self.label(wrapper,f"PILOTO NÍVEL {stats['level']}  •  {stats['xp']} XP  •  "
                   f"{stats['hours']:.1f} h  •  Habilitações: {', '.join(sorted(stats['qualifications']))}",
                   10,GREEN,True).pack(anchor="w",pady=(0,8))
        columns = ("kind", "origin", "destination", "pay", "minutes", "plane")
        table = ttk.Treeview(wrapper,columns=columns,show="headings",height=13,selectmode="browse")
        for key,title,width in [("kind","TIPO",240),("origin","SAÍDA",85),
                                 ("destination","DESTINO",100),("pay","PAGAMENTO",135),
                                 ("minutes","PREV. MIN",105),("plane","AVIÃO CONTRATANTE",200)]:
            table.heading(key,text=title)
            table.column(key,width=width,stretch=key in ("kind","plane"))
        table.pack(fill="both",expand=True)
        details = StringVar(value="Selecione uma missão. O pagamento requer voo completo e destino correto.")
        Label(wrapper,textvariable=details,bg=BG,fg=GOLD,font=(FONT,10),
              wraplength=980,justify="left",anchor="w").pack(fill="x",pady=10)
        offers_by_id = {}

        def selected(*_):
            keys=table.selection()
            if not keys:
                return
            m=offers_by_id[keys[0]]
            kind=TYPE_BY_CODE[m.category]
            plane=PLANE_BY_CODE[m.employer_plane].name if m.freelance else "Aeronave própria (frota futura)"
            details.set(f"{kind.title}: nível mínimo {kind.min_level}; {', '.join(kind.qualifications)}; "
                        f"{kind.min_hours:g}h.  {m.origin} → {m.destination}.  "
                        f"{plane}.  Freelancer: o piloto recebe salário, não compra o avião.")
        table.bind("<<TreeviewSelect>>",selected)

        def populate(force=False):
            for row in table.get_children():
                table.delete(row)
            offers_by_id.clear()
            now=time()
            if force or not self.storage.offer_cache_valid(center.icao, now):
                day=int(now//86400)
                # Uma geração por dia/região; clicando atualizar não cria infinitos contratos.
                offers=generate_offers(center,catalog,self.storage.pilot_stats(),
                            self.storage.owned_qualifications(),self.storage.family_experience(),day)
                emp_state=self.storage.employment_state()
                if emp_state['mode']=='empregado':
                    offers += generate_employer_routes(emp_state['employer_code'],center,catalog,
                        self.storage.pilot_stats(),self.storage.owned_qualifications(),
                        self.storage.family_experience(),day)
                self.storage.save_offers(center.icao, offers, now=now,
                                         valid_s=(day+1)*86400-now)
            for m in self.storage.active_offers(center.icao,now):
                if m.company_code and (self.storage.employment_state()['mode']!='empregado'
                    or self.storage.employment_state()['employer_code']!=m.company_code):
                    continue
                allowed,_=eligibility(m,self.storage.pilot_stats(),self.storage.owned_qualifications(),
                                      self.storage.family_experience())
                if not allowed:
                    continue
                offers_by_id[m.id]=m
                table.insert("", "end", iid=m.id, values=(TYPE_BY_CODE[m.category].title +
                    ("  •  FREELANCER" if m.freelance else ""),m.origin,m.destination,
                    brl(m.reward), f"~{estimated_minutes(distance_nm(m.origin_lat,m.origin_lon,m.destination_lat,m.destination_lon))}",
                    PLANE_BY_CODE[m.employer_plane].name if m.freelance else "—"))
            if not offers_by_id:
                details.set("Sem propostas disponíveis nesta região/nível. "
                    "Confira XP e habilitações ou tente outra base.")
            else:
                details.set(f"{len(offers_by_id)} propostas locais disponíveis. "
                            "As ofertas são atualizadas diariamente e não são criadas para outros aeroportos.")

        buttons=Frame(wrapper,bg=BG)
        buttons.pack(fill="x",pady=(5,0))
        def accept_selection():
            keys=table.selection()
            if not keys:
                messagebox.showinfo("Mercado", "Selecione uma proposta.",parent=window)
                return
            if self._accept_specific(offers_by_id[keys[0]]):
                window.destroy()
                self.market_dialog=None
        self.button(buttons,"Aceitar missão selecionada",accept_selection,accent=True).pack(side="left",padx=(0,9))
        self.button(buttons,"Atualizar lista",lambda:populate(True)).pack(side="left")
        self.button(buttons,"Vagas e companhias",self._employment_window).pack(side="left",padx=(8,0))
        self.label(buttons,"Apenas ofertas regionais; máximo 13 armazenadas.",9,MUTED).pack(side="right")
        populate()

    def _prepare_active_plan(self):
        m=self.career.mission
        if m is None:
            messagebox.showinfo('Plano VFR','Aceite primeiro um contrato.')
            return
        try:
            data=self._saved_preflight()
            path=export_vfr_plan(m,state_dir()/'planos_vfr', data.altitude_ft if data else 2500)
        except (OSError,ValueError) as exc:
            messagebox.showerror('Plano VFR',str(exc))
            return
        self._log(f'Plano VFR exportado: {path}')
        if self.mode != 'MSFS' or not self.connected:
            messagebox.showinfo('Plano preparado para o Mapa-Múndi',
                f'Plano exportado: {path}\n\nNo menu Mapa-Múndi do MSFS 2020, use Carregar/Salvar para abrir este .PLN e selecione manualmente a aeronave. '
                'Não existe integração testada para mudar automaticamente o avião pelo menu.')
            return
        if not messagebox.askyesno('Plano VFR criado',
            f'Plano salvo em:\n{path}\n\nSolicitar carregamento no MSFS agora?\n'
            'Isso altera a rota do simulador, mas NÃO troca a aeronave nem a posição.\n'
            'O GPS/mapa VFR pode exigir confirmação manual.'):
            return
        if not (self.mode=='MSFS' and self.connected and self.sim and self.last_sample
                and self.last_sample.on_ground and time()-self.last_sample.timestamp < 10):
            messagebox.showwarning('Plano VFR','Para carregar automaticamente, conecte o MSFS e mantenha o avião em solo. '
                'O arquivo .PLN já foi salvo e pode ser importado manualmente.')
            return
        self.sim.request_plan_load(path)
        self._log('Solicitação de carga do plano VFR enviada ao SimConnect. Aguardando retorno da API.')

    def _employment_window(self):
        if self.employment_dialog and self.employment_dialog.winfo_exists():
            self.employment_dialog.lift()
            return
        if self.storage.get_pilot() is None:
            messagebox.showwarning('Companhias','Cadastre teu piloto antes de concorrer a vagas.')
            return
        window=Toplevel(self.root)
        self.employment_dialog=window
        window.title('FlightSimCarreira • Modalidades de carreira e vagas')
        window.geometry('1050x720')
        window.minsize(850,610)
        window.configure(bg=BG)
        window.transient(self.root)
        window.protocol('WM_DELETE_WINDOW',lambda:(setattr(self,'employment_dialog',None),window.destroy()))
        wrapper=Frame(window,bg=BG,padx=20,pady=16)
        wrapper.pack(fill='both',expand=True)
        self.label(wrapper,'CARREIRA / EMPREGOS / COMPANHIA PRÓPRIA',16,CYAN,True).pack(anchor='w')
        self.label(wrapper,'Vagas geradas pelo jogo. GOL, Azul e LATAM não são parceiras nem anunciam vagas reais aqui.',
                   9,MUTED).pack(anchor='w',pady=(2,10))
        mode_text=StringVar()
        Label(wrapper,textvariable=mode_text,bg=BG,fg=GREEN,font=(FONT,12,'bold'),anchor='w').pack(fill='x')
        columns=('company','level','qualification','plane','salary','status')
        table=ttk.Treeview(wrapper,columns=columns,show='headings',height=8,selectmode='browse')
        for key,title,width in [('company','COMPANHIA',195),('level','NÍVEL',65),
                                ('qualification','HABILITAÇÕES',130),('plane','AVIÃO',120),
                                ('salary','REF. SALÁRIO',110),('status','REQUISITOS',260)]:
            table.heading(key,text=title)
            table.column(key,width=width,stretch=key in ('company','status'))
        table.pack(fill='both',expand=True,pady=(10,5))
        status=StringVar(value='Uma candidatura por semana. Resultado após virar o ciclo semanal UTC.')
        Label(wrapper,textvariable=status,bg=BG,fg=GOLD,font=(FONT,9),anchor='w',wraplength=980,
              justify='left').pack(fill='x',pady=6)
        options={}
        def redraw():
            now=time()
            period=weekly_period(now)
            state=self.storage.employment_state()
            label={'autonomo':'PILOTO AUTÔNOMO','empregado':'PILOTO CONTRATADO','empresario':'DONO DE COMPANHIA'}[state['mode']]
            suffix=(f" • {EMPLOYER_BY_CODE[state['employer_code']].name}" if state['employer_code'] in EMPLOYER_BY_CODE
                    else f" • {state['owner_company']}" if state['owner_company'] else '')
            mode_text.set(f'MODALIDADE ATUAL: {label}{suffix}')
            for item in table.get_children():
                table.delete(item)
            options.clear()
            region=(self.airport_catalog.nearest(self.last_sample.latitude,self.last_sample.longitude,6).icao
                    if self.airport_catalog and self.last_sample and
                    self.airport_catalog.nearest(self.last_sample.latitude,self.last_sample.longitude,6)
                    else self.storage.get_pilot()['home_icao'])
            for v in vacancies(period,region):
                ok,reason=employment_eligibility(v,self.storage.pilot_stats(),self.storage.owned_qualifications())
                options[v.id]=v
                co=EMPLOYER_BY_CODE[v.company]
                table.insert('', 'end',iid=v.id,values=(co.name,str(v.min_level),
                    ','.join(v.qualifications),v.plane,f'{brl(v.salary)}/sem',
                    'APTO' if ok else reason[:68]))
            latest=self.storage.list_applications()
            if latest:
                last=latest[0]
                status.set(f"Última candidatura: {last['company_code']} • {last['status']} • {last['vacancy_id']}. "
                           'Sem contratação real. As vagas são reiniciadas semanalmente.')
        def guard():
            if self.career.mission or self.tracker.phase==Phase.AIRBORNE:
                messagebox.showwarning('Carreira','Conclua/cancele o contrato e permaneça em solo antes de alterar vínculos.',parent=window)
                return False
            return True
        def apply():
            sel=table.selection()
            if not sel or not guard():
                return
            v=options[sel[0]]
            try:
                self.storage.apply_vacancy(v,time())
                self._log(f'INSCRIÇÃO: {EMPLOYER_BY_CODE[v.company].name}; resultado no fim da semana.')
                redraw()
            except ValueError as exc:
                messagebox.showwarning('Candidatura',str(exc),parent=window)
        def review():
            if not guard(): return
            results=self.storage.review_applications(time())
            if results:
                self.storage.invalidate_market()
            for result in results:
                self._log(f"SELEÇÃO DE EMPREGO: {result['company']} • {result['result']}")
            redraw()
            messagebox.showinfo('Recrutamento', 'Resultados atualizados. ' + (str(results) if results else 'Ainda aguardando fim do ciclo.'),parent=window)
        def resign():
            if not guard(): return
            if not messagebox.askyesno('Encerrar vínculo','Encerrar o vínculo e voltar a atuar como autônomo?',parent=window):return
            try:
                self.storage.resign_employment(time())
                self.storage.invalidate_market()
                self._log('Vínculo encerrado. Piloto voltou à modalidade autônoma.')
                redraw()
            except ValueError as exc:
                messagebox.showwarning('Companhias',str(exc),parent=window)
        actions=Frame(wrapper,bg=BG)
        actions.pack(fill='x',pady=(5,13))
        self.button(actions,'Candidatar-se',apply,accent=True).pack(side='left',padx=(0,6))
        self.button(actions,'Ver resultado / atualizar',review).pack(side='left',padx=(0,6))
        self.button(actions,'Pedir demissão',resign).pack(side='left')
        panel=self.section(wrapper,'ENDGAME • MINHA COMPANHIA AÉREA')
        panel.pack(fill='x')
        self.label(panel,f'A partir do nível {OWN_MIN_LEVEL}, 25 h, PLA e {brl(OWN_INVESTMENT)} de capital.',9,MUTED).pack(anchor='w')
        comp_name=StringVar(value='')
        entry=Entry(panel,textvariable=comp_name,font=(FONT,10),bg=PANEL2,fg=FG,insertbackground=FG,relief='flat')
        entry.pack(side='left',fill='x',expand=True,padx=(0,10),pady=5,ipady=7)
        def create_company():
            if not guard():return
            if not messagebox.askyesno('Criar companhia',f'Investir {brl(OWN_INVESTMENT)} para registrar a companhia virtual?',parent=window):return
            try:
                result=self.storage.found_company(comp_name.get(),time())
                self.career.balance=int(self.storage.get_setting('balance'))
                self.balance_var.set(brl(self.career.balance))
                self._log(f"COMPANHIA PRÓPRIA REGISTRADA: {result['owner_company']}")
                redraw()
            except ValueError as exc:
                messagebox.showwarning('Companhia',str(exc),parent=window)
        self.button(panel,'Fundar companhia',create_company,accent=True).pack(side='right')
        self.label(wrapper,'Registro inicial da companhia implementado; frota IA, pinturas, gestores e rotas empresariais são blocos futuros.',
                   9,MUTED).pack(anchor='w',pady=(8,0))
        redraw()

    def _cancel(self):
        self.career.cancel()
        self.storage.set_setting('preflight_v1','')
        self.realism_frozen=0.0
        self.realism_mission=None
        self.fuel_company_guard=None
        self._show_mission()
        self._checkpoint(force=True)
        self._log("Contrato cancelado. Não houve pagamento.")

    def _show_mission(self):
        m = self.career.mission
        self.mission_var.set((f"ATIVA  {m.origin} → {m.destination}  |  {brl(m.reward)}"
            + (f"  •  FREELANCER: {PLANE_BY_CODE[m.employer_plane].name}" if m.freelance else ""))
            if m else "Nenhum contrato ativo")

    def _checkpoint_data(self, tracker=None):
        return {"version": 1, "career": self.career.snapshot(),
                "tracker": (tracker or self.tracker).snapshot(),
                'realism_frozen':self.realism_frozen,
                'realism_mission':self.realism_mission,
                'fuel_penalty_frozen':self.fuel_penalty_frozen,
                'fuel_mode_at_takeoff':self.fuel_mode_at_takeoff,
                'fuel_ref_frozen':self.fuel_ref_frozen,
                'fuel_company_guard':self.fuel_company_guard}

    def _checkpoint(self, force=False):
        # Demo mantém o banco de carreira; checkpoint do voo é para modo MSFS.
        if self.mode == "Demo":
            return
        now = time()
        if force or now - self.last_checkpoint_time >= 2:
            self.storage.set_checkpoint(self._checkpoint_data())
            self.last_checkpoint_time = now

    def _save_log(self):
        path = state_dir() / "diagnostico_voo.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        info = ["FlightSimCarreira " + __version__, f"modo={self.mode}",
                f"fase={self.tracker.phase.value}",
                f"missao={self.career.snapshot()}",
                "LOG:", self.log_text.get("1.0", END)]
        path.write_text("\n".join(info), encoding="utf-8")
        self._log(f"Log salvo em {path}")
        messagebox.showinfo("Diagnóstico salvo", f"Arquivo local:\n{path}\n\nPode conter localização do voo; revise antes de compartilhar.")

    def _fuel_ref_for_sample(self,s):
        model=aircraft_model(s.aircraft_title)
        if not model:
            return None,None
        if self.career.mission and (self.career.mission.freelance or self.career.mission.company_code):
            self.fuel_company_guard=s.aircraft_title
            return 'contract:'+self.career.mission.id,model
        if self.career.mission:
            self.fuel_company_guard=None
        elif self.fuel_company_guard:
            if s.aircraft_title==self.fuel_company_guard:
                return None,None  # não injetar combustível próprio em avião do empregador
            self.fuel_company_guard=None
        fm=self.storage.fleet_manager()
        selected=fm.selected()
        if selected:
            if selected['code']!=model:
                return None,None  # nunca controlar combustível de outro modelo
            return selected['ref'],model
        if any(x['code']==model for x in self.storage.owned_fleet()):
            return 'legacy:'+model,model
        return None,None

    def _sync_fuel(self,s):
        if self.mode!='MSFS' or s.fuel_tanks is None:
            return
        if s.unlimited_fuel:
            if time()-self.fuel_warning_at>30:
                self._log('Combustível ilimitado está ativo no MSFS: desative essa assistência para controlar o consumo.')
                self.fuel_warning_at=time()
            return
        ref,model=self._fuel_ref_for_sample(s)
        if not ref:
            return
        enabled=self.storage.get_setting('fuel_control_enabled')=='1'
        try:
            status,correction=self.fuel_manager.observe(ref,model,s.fuel_tanks,s.fuel_gallons,
                s.on_ground,s.fuel_tank_capacities,enabled)
        except (ValueError, TypeError, OSError) as exc:
            if time()-self.fuel_warning_at>=30:
                self._log('Combustível: monitoramento indisponível: '+str(exc))
                self.fuel_warning_at=time()
            return
        if correction and self.sim and self.connected:
            self.sim.request_fuel_restore(correction)
            if time()-self.fuel_warning_at>=12:
                self._log(f'COMBUSTÍVEL: correção solicitada para {ref} ({sum(correction.values()):.1f} gal).')
                self.fuel_warning_at=time()
        elif status in ('unsupported','mismatch','uninitialized','write_not_confirmed','read_only') and time()-self.fuel_warning_at>=35:
            self._log('COMBUSTÍVEL: sincronização indisponível para esta aeronave/leitura. Sem escrita de tanques.')
            self.fuel_warning_at=time()
        elif status=='calibrated':
            self._log(f'COMBUSTÍVEL: {sum(s.fuel_tanks.values()):.1f} gal registrados no addon ({ref}).')

    def _process_sample(self,s):
        self.last_sample=s
        self._sync_fuel(s)
        fmt=lambda n: f"{n:,.0f}"
        for key,val in {
            "ias":fmt(s.ias_kt),"gs":fmt(s.groundspeed_kt) + ("~" if s.groundspeed_estimated else ""),
            "agl":fmt(s.agl_ft),"alt":fmt(s.altitude_ft),
            "vs":f"{s.vs_fpm:+,.0f}",
            "lat":f"{s.latitude:.5f}","lon":f"{s.longitude:.5f}",
            "fuel":f"{s.fuel_gallons:.1f}" if s.fuel_gallons is not None else "—"}.items():
            self.flight_vars[key].set(val)
        previous_phase = self.tracker.phase
        old_career_state = self.career.snapshot()
        mission_before=self.career.mission
        old_balance = self.career.balance
        events = self.tracker.update(s)
        completion_payment = self.career.evaluate(events, s.aircraft_title)
        self.phase_var.set(self.tracker.phase.value.upper())
        for e in events:
            if e["type"] == "takeoff":
                self._log("DECOLAGEM detectada. Diário iniciado e salvo para recuperação.")
                self.realism_frozen=0.0
                self.realism_mission=None
                self.fuel_penalty_frozen=(.3 if self.storage.get_setting('fuel_control_enabled')=='0' else 0.0)
                ref,model=self._fuel_ref_for_sample(s)
                self.fuel_ref_frozen=ref
                self.fuel_mode_at_takeoff=bool(self.fuel_penalty_frozen==0 and ref and self.fuel_manager.get(ref))
                if self.fuel_penalty_frozen:
                    self._log('Combustível sob controle do MSFS: penalidade -30% sobre R$ e XP deste voo.')
                plan=self._saved_preflight()
                if plan and self.career.mission:
                    try:
                        # São usados valores DO INÍCIO DO VOO, não leituras antigas
                        # do checklist. Se o piloto mudou aeronave, não há bônus.
                        if not aircraft_title_matches(plan.aircraft_title, s.aircraft_title):
                            self._log('Despacho: avião diferente da seleção; bônus desativado.')
                        else:
                            snapshot=replace(plan,
                                planned_fuel_gal=s.fuel_gallons,
                                planned_weight_lbs=s.total_weight_lbs,
                                max_weight_lbs=s.max_gross_weight_lbs,
                                real_time_declared=(plan.real_time_declared and
                                    (s.sim_rate is None or 0.99 <= s.sim_rate <= 1.01)))
                            details=inspect_preflight(self.career.mission,snapshot)
                            self.realism_frozen=details['bonus_fraction']
                            self.realism_mission=self.career.mission.id
                            self._log(f'Despacho: bônus de {self.realism_frozen:.0%} congelado na decolagem (dados disponíveis).')
                    except ValueError as exc:
                        self._log('Despacho indisponível: '+str(exc))
                if self.career.mission and self.career.mission.freelance and not self.career.employer_aircraft_confirmed:
                    self._log("ALERTA FREELANCER: modelo não confirmado na decolagem; sem pagamento até próximo voo correto.")
                self._checkpoint(force=True)
            elif e["type"] == "landing":
                v=e["touchdown_fpm_est"]
                self._log(f"POUSO confirmado. Razão vertical aproximada: {v:.0f} ft/min" if v is not None else "POUSO confirmado (razão vertical indisponível).")
                start = next((item for item in self.tracker.events if item["type"] == "takeoff"), None)
                if start is None:
                    self._log("ERRO: decolagem anterior indisponível. Mantendo estado para diagnóstico.")
                    continue
                payment = completion_payment
                next_tracker = FlightTracker()
                next_tracker.update(s)
                checkpoint_after = self._checkpoint_data(tracker=next_tracker)
                checkpoint_after['realism_frozen']=0.0
                checkpoint_after['realism_mission']=None
                checkpoint_after['fuel_penalty_frozen']=0.0
                checkpoint_after['fuel_mode_at_takeoff']=False
                checkpoint_after['fuel_ref_frozen']=None
                realism_fraction=(self.realism_frozen if payment and
                                  self.realism_mission==payment['mission'] else 0.0)
                # Detecta aeródromo realmente alcançado mesmo em voo sem contrato.
                if self.airport_catalog is None:
                    from .contracts import AirportCatalog
                    self.airport_catalog=AirportCatalog()
                located=self.airport_catalog.nearest(s.latitude,s.longitude,3)
                landing_icao=located.icao if located else (
                    mission_before.destination if payment and mission_before else None)
                try:
                    inserted = self.storage.finalize_flight(start, e, v, self.tracker.stalls,
                                        payment["mission"] if payment else None,
                                        payment["reward"] if payment else 0, checkpoint_after,
                                        aircraft_title=s.aircraft_title,
                                        fuel_start=(self.tracker.takeoff_sample.fuel_gallons
                                                    if self.tracker.takeoff_sample else None),
                                        fuel_end=s.fuel_gallons,
                                        realism_fraction=realism_fraction,
                                        destination=landing_icao,
                                        fuel_penalty_fraction=self.fuel_penalty_frozen,
                                        fuel_prepaid=self.fuel_mode_at_takeoff)
                except Exception as exc:
                    self._log(f"FALHA AO SALVAR pouso: {exc}. Não feche antes de exportar log.")
                    self.status_var.set("Erro ao salvar voo")
                    self.career.restore(old_career_state)
                    self.career.balance = old_balance
                    # O checkpoint anterior mantém a fase em voo; ao reiniciar,
                    # o app poderá confirmar novamente o pouso em solo.
                    return
                self.tracker = next_tracker
                self.realism_frozen=0.0
                self.realism_mission=None
                self.fuel_penalty_frozen=0.0
                self.fuel_mode_at_takeoff=False
                self.fuel_ref_frozen=None
                self.career.balance = int(self.storage.get_setting("balance") or 0)
                summary = self.storage.flight_finance(start)
                actual_credit = self.career.balance - old_balance
                if inserted and self.storage.get_pilot() is not None:
                    base_xp=flight_xp(payment['reward'] if payment else 0)
                    bonus_xp=round(base_xp*realism_fraction) if payment else 0
                    # valor congelado antes de limpar o estado
                    earned=self.storage.conn.execute('SELECT xp FROM pilot_xp_ledger WHERE flight_key=?',
                        (f"takeoff:{float(start['timestamp']):.6f}:{float(start['lat']):.7f}:{float(start['lon']):.7f}",)).fetchone()
                    self._log(f"PROGRESSO DO PILOTO: +{earned[0] if earned else 0} XP ({bonus_xp} potencial do despacho).")
                    self._refresh_pilot_summary()
                if not inserted:
                    self._log("Pouso já salvo anteriormente: pagamento duplicado bloqueado.")
                    saved = self.storage.get_checkpoint()
                    if saved:
                        self.career.restore(saved.get("career", {}))
                elif payment and summary['gross'] > 0:
                    self._log(f"CONTRATO CONCLUÍDO: {brl(summary['gross'])} bruto; {brl(summary['expenses'])} de custos; líquido {brl(summary['net'])}.")
                elif payment:
                    self._log("Contrato já pago anteriormente. Novo crédito bloqueado.")
                else:
                    self._log("Voo registrado; contrato não concluído (confira origem e destino).")
                self.balance_var.set(brl(self.career.balance))
                if inserted and payment:
                    self.storage.set_setting('preflight_v1','')
                self._show_mission()
                self.phase_var.set(self.tracker.phase.value.upper())
                self._refresh_history()
                self.last_checkpoint_time = time()
            elif e["type"] == "stall_warning":
                self._log("AVISO DE ESTOL detectado (não é penalidade automática).")
        if previous_phase != self.tracker.phase or self.career.mission and events:
            self._checkpoint(force=True)
        else:
            self._checkpoint()

    def _publish_bridge(self):
        m=self.career.mission
        s=self.last_sample if self.connected else None
        mission=None
        if m:
            a,b=AIRPORTS.get(m.origin),AIRPORTS.get(m.destination)
            mission={'origin':m.origin,'destination':m.destination,'title':m.title,
                     'reward':m.reward,'origin_lat':m.origin_lat if m.origin_lat is not None else (a.latitude if a else None),
                     'origin_lon':m.origin_lon if m.origin_lon is not None else (a.longitude if a else None),
                     'destination_lat':m.destination_lat if m.destination_lat is not None else (b.latitude if b else None),
                     'destination_lon':m.destination_lon if m.destination_lon is not None else (b.longitude if b else None)}
        self.bridge_state.update(status='connected' if s else 'offline',
            phase=self.tracker.phase.value,balance=self.career.balance,
            aircraft=s.aircraft_title if s else None,
            position={'lat':s.latitude,'lon':s.longitude} if s else None,
            fuel_gallons=s.fuel_gallons if s else None,
            mission=mission,updated=time())

    def _open_local_panel(self):
        import webbrowser
        if self.bridge_error:
            messagebox.showwarning('Painel local','Não foi possível iniciar a ponte: '+self.bridge_error)
            return
        self._publish_bridge()
        webbrowser.open('http://127.0.0.1:8769/')
        self._log('Painel local aberto no navegador. Para o usar na toolbar, compilar in_game/toolbar com SDK MSFS 2020.')

    def _poll(self):
        try:
            while True:
                kind,item,generation=self.queue.get_nowait()
                if self.mode!="MSFS" or generation != self.session_generation:
                    continue
                if kind=="sample": self._process_sample(item)
                elif kind=="connected":
                    self.connected=True
                    self.status_var.set(item)
                    self._log(item)
                elif kind=="error":
                    self.connected=False
                    self.status_var.set("Adaptador indisponível")
                    self._log(item)
                elif kind=="warning":
                    self.status_var.set("Monitorando / recuperação")
                    self._log(item)
                elif kind=='plan_loaded':
                    self._log(item)
                    messagebox.showinfo('SimConnect / plano VFR',item)
                elif kind=='fuel_sent':
                    self._log('Combustível: solicitação enviada ao MSFS; leitura posterior confirmará.')
                elif kind=='fuel_error':
                    self._log('ALERTA combustível: escrita recusada: '+item)
                elif kind=='plan_error':
                    self._log('PLANO VFR: '+item)
                    messagebox.showwarning('Plano VFR',item)
                elif kind=="disconnected":
                    self.connected=False
                    self.status_var.set(item)
        except Empty:
            pass
        self._publish_bridge()
        self.root.after(200,self._poll)

    def _finance_window(self):
        """Operações financeiras opcionais, 100% no banco do addon.

        Não abastece nem repara fisicamente o avião no MSFS, nem injeta falhas.
        """
        if self.finance_dialog is not None and self.finance_dialog.winfo_exists():
            self.finance_dialog.lift()
            return
        window = Toplevel(self.root)
        self.finance_dialog = window
        window.title("FlightSimCarreira • Finanças, frota e manutenção")
        window.geometry("980x730")
        window.minsize(800,650)
        window.configure(bg=BG)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, "finance_dialog", None), window.destroy()))

        main=Frame(window,bg=BG,padx=20,pady=16)
        main.pack(fill="both",expand=True)
        self.label(main,"FINANÇAS E HANGAR / BLOCO 04",17,CYAN,True).pack(anchor="w")
        balance_text=StringVar()
        self.label(main,"CUSTOS VIRTUAIS — combustível do jogo não altera tanques do MSFS.",9,MUTED).pack(anchor="w",pady=(3,9))
        Label(main,textvariable=balance_text,bg=BG,fg=GREEN,font=(FONT,14,"bold"),anchor="w").pack(fill="x")
        fleet_panel=self.section(main,"AERONAVES PRÓPRIAS E MANUTENÇÃO")
        fleet_panel.pack(fill="x",pady=(10,10))
        fleet_info=StringVar(value="")
        Label(fleet_panel,textvariable=fleet_info,justify="left",anchor="w",bg=PANEL,fg=FG,
              font=(FONT,10),wraplength=895).pack(fill="x",pady=(2,8))
        bar=Frame(fleet_panel,bg=PANEL)
        bar.pack(fill="x",pady=(0,8))
        plane_var=StringVar(value="c152")
        choices=ttk.Combobox(bar,textvariable=plane_var,state="readonly",width=28,
                values=[f'{code} | {model.title}' for code,model in AIRCRAFT_ECONOMY.items()])
        choices.current(0)
        choices.pack(side="left",padx=(0,8))
        def code(): return plane_var.get().split(' | ',1)[0]
        plane_price_var=StringVar()
        def update_price(*_):
            plane_price_var.set('Valor no jogo: '+brl(AIRCRAFT_ECONOMY[code()].purchase_price))
        choices.bind('<<ComboboxSelected>>',update_price)
        Label(bar,textvariable=plane_price_var,bg=PANEL,fg=GOLD,font=(FONT,9)).pack(side='left')
        update_price()
        def transact(operation):
            if self.tracker.phase == Phase.AIRBORNE:
                messagebox.showwarning('Finanças','Faça operações de hangar somente em solo.',parent=window)
                return
            try:
                result=operation()
                self.career.balance=int(self.storage.get_setting('balance') or 0)
                self.balance_var.set(brl(self.career.balance))
                redraw()
                if result is False:
                    messagebox.showinfo('Finanças','Aeronave inicial já resgatada.',parent=window)
            except (ValueError, KeyError) as exc:
                messagebox.showwarning('Finanças',str(exc),parent=window)
        actions=Frame(fleet_panel,bg=PANEL)
        actions.pack(fill="x")
        self.button(actions,'Resgatar C152 inicial',lambda:transact(self.storage.claim_starter),accent=True).pack(side="left",padx=(0,7))
        self.button(actions,'Frota avançada',self._fleet_window,accent=True).pack(side='left',padx=(0,7))
        self.button(actions,'Comprar modelo',lambda:transact(lambda:self.storage.buy_aircraft(code())) if messagebox.askyesno('Comprar aeronave', f'Comprar {AIRCRAFT_ECONOMY[code()].title} por {brl(AIRCRAFT_ECONOMY[code()].purchase_price)}?',parent=window) else None).pack(side="left",padx=(0,7))
        self.button(actions,'Revisão completa',lambda:transact(lambda:self.storage.service_aircraft(code()))).pack(side="left",padx=(0,7))
        self.button(actions,'Alternar seguro',lambda:transact(lambda:self.storage.set_insurance(code(),
            not next((p['insured'] for p in self.storage.owned_fleet() if p['code']==code()),False)))).pack(side="left")
        finances=self.section(main,"FINANCIAMENTO E EXTRATO")
        finances.pack(fill="both",expand=True)
        top=Frame(finances,bg=PANEL)
        top.pack(fill="x",pady=(0,8))
        self.button(top,'Crédito de R$ 10.000',lambda:transact(lambda:self.storage.take_loan(10000)) if messagebox.askyesno('Financiamento', 'Receber R$ 10.000 e assumir dívida total de R$ 10.800?',parent=window) else None).pack(side="left",padx=(0,8))
        self.button(top,'Pagar parcela R$ 1.000',lambda:transact(lambda:self.storage.repay_loan(
            min(1000,self.storage.outstanding_loan())))).pack(side="left",padx=(0,8))
        self.label(top,'Taxa fixa 8% por operação; sem juros recorrentes nesta versão.',9,MUTED).pack(side="left")
        history=Text(finances,bg=PANEL2,fg=FG,insertbackground=CYAN,font=("Consolas",10),height=12,
                 relief="flat",state="disabled",wrap="word")
        history.pack(fill="both",expand=True)
        opts=Frame(main,bg=BG)
        opts.pack(fill='x',pady=(9,0))
        tax_var=IntVar(value=int(self.storage.get_setting('income_tax_enabled') or '0'))
        fault_var=IntVar(value=int(self.storage.get_setting('simulated_failures_enabled') or '0'))
        def save_option(key,var):
            self.storage.set_setting(key, str(int(var.get())))
        Checkbutton(opts,text='Taxa virtual de 4% sobre contratos',variable=tax_var,
                    command=lambda:save_option('income_tax_enabled',tax_var),bg=BG,fg=FG,
                    selectcolor=PANEL,activebackground=BG,activeforeground=FG).pack(side='left',padx=(0,12))
        Checkbutton(opts,text='Permitir falhas (preparação; ainda não injeta)',variable=fault_var,
                    command=lambda:save_option('simulated_failures_enabled',fault_var),bg=BG,fg=FG,
                    selectcolor=PANEL,activebackground=BG,activeforeground=FG).pack(side='left')
        fuel_opts=Frame(main,bg=BG);fuel_opts.pack(fill='x',pady=(5,0))
        fuel_var=IntVar(value=int(self.storage.get_setting('fuel_control_enabled') or '0'))
        def change_fuel_mode():
            if self.tracker.phase==Phase.AIRBORNE:
                messagebox.showwarning('Combustível','Altere apenas em solo; o modo fica congelado na decolagem.',parent=window)
                fuel_var.set(int(self.storage.get_setting('fuel_control_enabled') or '0'))
                return
            self.storage.set_setting('fuel_control_enabled',str(int(fuel_var.get())))
            self._log('Controle combustível '+('ATIVO' if fuel_var.get() else 'DESLIGADO: -30% R$/XP nos próximos voos'))
        Checkbutton(fuel_opts,text='Combustível controlado pelo FlightSimCarreira',variable=fuel_var,
                    command=change_fuel_mode,bg=BG,fg=FG,selectcolor=PANEL,
                    activebackground=BG,activeforeground=FG).pack(side='left',padx=(0,12))
        self.label(fuel_opts,'Desligado: -30% dinheiro e XP. Com controle ativo, abasteça pela Frota avançada.',
                   9,GOLD).pack(side='left')

        def redraw():
            balance_text.set(f"Saldo: {brl(int(self.storage.get_setting('balance') or 0))}    •    "
                             f"Dívida: {brl(self.storage.outstanding_loan())}")
            fleet=self.storage.owned_fleet()
            fleet_info.set('   |   '.join(f"{p['name']}: {p['condition']:.1f}% • {p['hours']:.1f} h • "
                         f"{'segurado' if p['insured'] else 'sem seguro'}" for p in fleet)
                         if fleet else 'Nenhuma aeronave própria cadastrada. Resgate seu Cessna 152 inicial.')
            history.configure(state='normal')
            history.delete('1.0',END)
            for e in self.storage.finance_history():
                history.insert(END,f"{strftime('%d/%m %H:%M',localtime(e['occurred_utc']))}  "
                               f"{brl(e['amount']):>12}  {e['description']}\n")
            if not self.storage.finance_history():
                history.insert(END,'Sem movimentos novos. Voos anteriores à v0.5.0 não foram cobrados.\n')
            history.configure(state='disabled')
        redraw()

    def _saved_preflight(self, mission_id=None):
        raw=self.storage.get_setting('preflight_v1')
        current_id = mission_id or (self.career.mission.id if self.career.mission else None)
        if not raw or current_id is None:
            return None
        try:
            data=Preflight(**json.loads(raw))
            return data if data.mission_id==current_id else None
        except (TypeError, ValueError, KeyError):
            return None

    def _planning_window(self):
        if not self.career.mission:
            messagebox.showinfo('Despacho','Aceite primeiro um contrato regional ou freelancer.')
            return
        if self.planning_dialog is not None and self.planning_dialog.winfo_exists():
            self.planning_dialog.lift();return
        m=self.career.mission
        window=Toplevel(self.root)
        self.planning_dialog=window
        window.title('FlightSimCarreira • Despacho pré-voo')
        window.geometry('900x760');window.minsize(760,650);window.configure(bg=BG)
        window.protocol('WM_DELETE_WINDOW',lambda:(setattr(self,'planning_dialog',None),window.destroy()))
        body=Frame(window,bg=BG,padx=24,pady=18);body.pack(fill='both',expand=True)
        self.label(body,f'DESPACHO / {m.origin} → {m.destination}',17,CYAN,True).pack(anchor='w')
        self.label(body,'Pontos verificados pelo MSFS são diferentes das declarações do piloto.',9,MUTED).pack(anchor='w',pady=(2,12))
        saved=self._saved_preflight()
        model_name=(self.last_sample.aircraft_title if self.last_sample and self.last_sample.aircraft_title else
                    (saved.aircraft_title if saved else 'Cessna 152'))
        fleet=self.storage.fleet_manager()
        selected=fleet.selected()
        airplane=StringVar(value=selected['title'] if selected else model_name)
        self.label(body,'AERONAVE DESIGNADA / SELECIONADA',10,GOLD,True).pack(anchor='w')
        Entry(body,textvariable=airplane,fg=FG,bg=PANEL2,insertbackground=FG,
              relief='flat',font=(FONT,11)).pack(fill='x',pady=(4,7))
        if m.freelance:
            self.label(body,'Freelancer: usar aeronave do contratante. A troca de avião no MSFS ainda é manual.',9,GOLD).pack(anchor='w')
        self.label(body,'CHECKLIST: confirme somente o que realmente foi configurado/conferido no MSFS.',9,MUTED).pack(anchor='w',pady=(9,7))
        items=[('real_weather_declared','Clima ao vivo (confirmação manual)'),
            ('real_time_declared','Horário real (confirmação manual)'),
            ('assists_realistic_declared','Assistências realistas (confirmação manual)'),
            ('runway_checked','Pista e iluminação verificadas no mapa/aviação'),
            ('route_checked','Rota e altitude revisadas no mapa VFR/GPS'),
            ('fuel_checked','Combustível e reserva conferidos'),
            ('payload_checked','Peso e balanceamento verificados')]
        flags={key:IntVar(value=int(bool(getattr(saved,key,False)))) for key,_ in items}
        for key,caption in items:
            Checkbutton(body,text=caption,variable=flags[key],bg=BG,fg=FG,
                selectcolor=PANEL2,activebackground=BG,activeforeground=FG,
                font=(FONT,10)).pack(anchor='w',pady=1)
        altitude=StringVar(value=str(saved.altitude_ft if saved else 2500))
        self.label(body,'Altitude de cruzeiro (ft)',9,MUTED).pack(anchor='w',pady=(11,2))
        Entry(body,textvariable=altitude,width=14,bg=PANEL2,fg=FG,insertbackground=FG).pack(anchor='w')
        report=Text(body,bg=PANEL2,fg=FG,height=9,font=('Consolas',10),relief='flat',wrap='word',padx=12,pady=9)
        report.pack(fill='both',expand=True,pady=(12,10))
        def build():
            s=self.last_sample
            if self.mode=='MSFS' and s and time()-s.timestamp<12 and s.on_ground:
                fuel=s.fuel_gallons
                weight=s.total_weight_lbs
                maxweight=s.max_gross_weight_lbs
            else:
                fuel=weight=maxweight=None
            return Preflight(m.id,airplane.get().strip(),**{key:bool(v.get()) for key,v in flags.items()},
                planned_fuel_gal=fuel,planned_weight_lbs=weight,max_weight_lbs=maxweight,
                altitude_ft=int(altitude.get()))
        def review(save=False):
            if self.tracker.phase==Phase.AIRBORNE:
                messagebox.showwarning('Despacho','Conclua o voo antes de mudar os critérios do contrato.',parent=window);return
            try:
                plan=build()
                details=inspect_preflight(m,plan)
                if save:
                    self.storage.set_setting('preflight_v1',json.dumps(plan.snapshot(),ensure_ascii=False))
                    self._log(f'Despacho salvo para {m.origin} → {m.destination}, bônus previsto até {details["bonus_fraction"]:.0%} (condicionado ao pouso).')
                report.delete('1.0',END)
                report.insert(END,f'Distância: {details["distance_nm"]} NM\nDuração estimada: {details["minutes"]} min\n')
                report.insert(END,f'Combustível mínimo estimado (inclui margem): {details["fuel_required_gal"]} gal\n')
                for key,val in details['components'].items():
                    report.insert(END,f'{"OK" if val["ok"] else "PENDENTE"}: {key} (+{val["rate"]*100:g}%)\n')
                report.insert(END,f'\nBônus previsto: +{details["bonus_fraction"]*100:.1f}% sobre pagamento e XP do contrato\n')
                report.insert(END,'Clima/horário/assistências/pista são declarações do piloto, NÃO telemetria validada.\n')
                if save:
                    messagebox.showinfo('Despacho','Checklist salvo. Os valores medidos foram congelados em solo; confirme as opções declaradas.',parent=window)
            except (ValueError,TypeError) as exc:
                messagebox.showwarning('Despacho',str(exc),parent=window)
        bar=Frame(body,bg=BG);bar.pack(fill='x')
        self.button(bar,'Revisar',lambda:review(False)).pack(side='left',padx=(0,8))
        self.button(bar,'Salvar checklist',lambda:review(True),accent=True).pack(side='left',padx=(0,8))
        self.button(bar,'Exportar/Carregar .PLN',self._prepare_active_plan).pack(side='left')
        review(False)

    def _fleet_window(self):
        if self.fleet_dialog is not None and self.fleet_dialog.winfo_exists():
            self.fleet_dialog.lift();return
        window=Toplevel(self.root);self.fleet_dialog=window
        window.title('FlightSimCarreira • Frota 2.0 e aeronaves do MSFS')
        window.geometry('1050x730');window.minsize(890,630);window.configure(bg=BG)
        window.protocol('WM_DELETE_WINDOW',lambda:(setattr(self,'fleet_dialog',None),window.destroy()))
        main=Frame(window,bg=BG,padx=20,pady=14);main.pack(fill='both',expand=True)
        self.label(main,'FROTA  /  NOVAS, USADAS, ALUGUEL E VENDA',16,CYAN,True).pack(anchor='w')
        self.label(main,'Transações virtuais; o MSFS não troca o avião automaticamente.',9,MUTED).pack(anchor='w',pady=(4,10))
        cols=('ref','code','title','kind','condition','location')
        view=ttk.Treeview(main,columns=cols,show='headings',height=9,selectmode='browse')
        for key,title,w in [('ref','ID',105),('code','MODELO',65),('title','AERONAVE',245),
                            ('kind','AQUISIÇÃO',125),('condition','ESTADO',95),('location','AERÓDROMO',100)]:
            view.heading(key,text=title);view.column(key,width=w,stretch=key=='title')
        view.pack(fill='x')
        fm=self.storage.fleet_manager()
        balance=StringVar()
        Label(main,textvariable=balance,bg=BG,fg=GREEN,font=(FONT,11,'bold')).pack(anchor='w',pady=(8,5))
        airport=StringVar(value=(self.storage.get_pilot() or {}).get('home_icao','SBRF'))
        line=Frame(main,bg=BG);line.pack(fill='x',pady=(3,10))
        self.label(line,'Aeroporto:',9,MUTED).pack(side='left')
        Entry(line,textvariable=airport,width=7,bg=PANEL2,fg=FG,insertbackground=FG).pack(side='left',padx=6)
        model=StringVar(value='c152')
        models=ttk.Combobox(line,textvariable=model,state='readonly',width=24,
                  values=[f'{code} | {p.title}' for code,p in AIRCRAFT_ECONOMY.items()])
        models.current(0);models.pack(side='left',padx=7)
        def code():return model.get().split(' | ',1)[0]
        def chosen():
            ids=view.selection()
            return ids[0] if ids else None
        def at_home():
            location=airport.get().strip().upper()
            if len(location)!=4 or not location.isalpha():raise ValueError('Informe ICAO válido.')
            return location
        def redraw():
            for row in view.get_children():view.delete(row)
            for plane in fm.all():
                view.insert('','end',iid=plane['ref'],values=(plane['ref'],plane['code'],plane['title'],plane['kind'],
                    f"{plane['condition']:.1f}%",plane['airport']))
            selected=fm.selected()
            balance.set(f"Caixa: {brl(int(self.storage.get_setting('balance') or 0))}  •  Selecionado: {selected['title'] if selected else 'nenhum'}")
        def op(fn):
            if self.tracker.phase==Phase.AIRBORNE:
                messagebox.showwarning('Frota','Faça transações somente em solo.',parent=window);return
            try:
                item=fn()
                self.career.balance=int(self.storage.get_setting('balance') or 0)
                self.balance_var.set(brl(self.career.balance))
                redraw();return item
            except (ValueError,KeyError) as exc:
                messagebox.showwarning('Frota',str(exc),parent=window)
        buttons=Frame(main,bg=BG);buttons.pack(fill='x',pady=(0,10))
        self.button(buttons,'Selecionar para voo',lambda:op(lambda:fm.select(chosen()))).pack(side='left',padx=(0,6))
        self.button(buttons,'Comprar nova',lambda:op(lambda:fm.purchase(code(),at_home())) if messagebox.askyesno('Compra nova',f'Comprar {AIRCRAFT_ECONOMY[code()].title} por {brl(AIRCRAFT_ECONOMY[code()].purchase_price)}?',parent=window) else None).pack(side='left',padx=(0,6))
        self.button(buttons,'Alugar 24h',lambda:op(lambda:fm.rent(code(),at_home()))).pack(side='left',padx=(0,6))
        self.button(buttons,'Vender escolhida',lambda:op(lambda:fm.sell(chosen())) if messagebox.askyesno('Vender','Vender aeronave selecionada? Valor de revenda abaixo do preço de compra.',parent=window) else None).pack(side='left',padx=(0,6))
        self.button(buttons,'Revisar escolhida',lambda:op(lambda:fm.service(chosen()))).pack(side='left')
        def refuel():
            if not (self.mode=='MSFS' and self.connected and self.last_sample
                    and self.last_sample.on_ground and time()-self.last_sample.timestamp<10):
                messagebox.showwarning('Combustível','Conecte o MSFS com a aeronave no solo.',parent=window);return
            ref=chosen()
            if not ref or not fm.get(ref):
                messagebox.showwarning('Combustível','Selecione uma aeronave própria/alugada.',parent=window);return
            model=aircraft_model(self.last_sample.aircraft_title)
            if fm.get(ref)['code']!=model:
                messagebox.showwarning('Combustível','O modelo selecionado deve estar carregado no MSFS.',parent=window);return
            if not messagebox.askyesno('Abastecimento','Completar os tanques registrados, cobrando em R$ da carreira?',parent=window):return
            result=op(lambda:self.fuel_manager.refuel_full(ref))
            if result:
                self._log(f"ABASTECIMENTO: +{result['added_gal']:.1f} gal por {brl(result['cost_brl'])}.")
        self.button(buttons,'Abastecer',refuel,accent=True).pack(side='left',padx=(6,0))
        market=self.section(main,'MERCADO DE SEGUNDA MÃO (ATUALIZA SEMANALMENTE)')
        market.pack(fill='both',expand=True)
        second=ttk.Treeview(market,columns=('title','cond','hours','price'),show='headings',height=5)
        for col,title in [('title','AERONAVE'),('cond','ESTADO'),('hours','HORAS'),('price','PREÇO')]:
            second.heading(col,text=title);second.column(col,width=145,stretch=True)
        second.pack(fill='x')
        def refresh_used():
            for row in second.get_children():second.delete(row)
            offers=used_market(at_home(),int(time()//(7*86400)))
            for offer in offers:
                second.insert('','end',iid=offer.offer_id,values=(offer.title,
                    f'{offer.condition:.1f}%',f'{offer.hours:.0f} h',brl(offer.price)))
            return {x.offer_id:x for x in offers}
        offered={}
        def update_offers():
            try:
                offered.clear();offered.update(refresh_used())
            except ValueError as exc:messagebox.showwarning('Mercado',str(exc),parent=window)
        def buy_used():
            row=second.selection()
            if not row:return
            offer=offered[row[0]]
            if messagebox.askyesno('Comprar usada',f'{offer.title}, {offer.condition:.1f}% de estado, {brl(offer.price)}?',parent=window):
                op(lambda:fm.purchase(offer.code,at_home(),offer=offer))
        row=Frame(market,bg=PANEL);row.pack(fill='x',pady=(6,0))
        self.button(row,'Comprar usada selecionada',buy_used,accent=True).pack(side='left',padx=(0,8))
        self.button(row,'Atualizar mercado local',update_offers).pack(side='left',padx=(0,8))
        self.button(row,'Aeronaves instaladas no MSFS',self._installed_aircraft_window).pack(side='left')
        redraw();update_offers()

    def _installed_aircraft_window(self):
        win=Toplevel(self.root);win.title('FlightSimCarreira • Aeronaves instaladas MSFS 2020')
        win.geometry('910x630');win.configure(bg=BG)
        panel=Frame(win,bg=BG,padx=16,pady=14);panel.pack(fill='both',expand=True)
        self.label(panel,'INVENTÁRIO LOCAL DO SIMULADOR',16,CYAN,True).pack(anchor='w')
        self.label(panel,'Community + Official: instalação detectada ≠ prova de posse/licença no MSFS.',9,MUTED).pack(anchor='w',pady=(2,8))
        status=StringVar(value='Clique em Escanear.')
        Label(panel,textvariable=status,bg=BG,fg=GOLD,font=(FONT,9)).pack(anchor='w')
        box=Text(panel,bg=PANEL2,fg=FG,font=('Consolas',10),height=18,relief='flat',wrap='none')
        box.pack(fill='both',expand=True,pady=(7,8))
        def search():
            from tkinter import filedialog
            roots=detect_package_roots()
            if not roots:
                path=filedialog.askdirectory(title='Selecione pasta InstalledPackages do MSFS')
                if not path:return
                roots=[Path(path)]
            items=scan_installed_aircraft(roots)
            box.delete('1.0',END)
            for x in items:
                box.insert(END,f'{x.title} | {x.ui_variation} | {x.source}\n')
            status.set(f'{len(items)} títulos/variações encontrados em '+', '.join(str(x) for x in roots))
            if not items:box.insert(END,'Nenhum aircraft.cfg legível. Marketplace pode estar protegido; confira a pasta de instalação.\n')
        self.button(panel,'Escanear aeronaves instaladas',search,accent=True).pack(anchor='w')

    def _locate_neofly(self):
        paths = discover_neofly_databases()
        if paths:
            detail = "\n".join(str(path) for path in paths[:20])
            self._log(f"Busca NeoFly: {len(paths)} arquivo(s) encontrado(s).")
            messagebox.showinfo("Arquivos NeoFly encontrados", detail +
                "\n\nSelecione o arquivo desejado em Analisar common.db / std.bin."
            )
        else:
            self._log("Busca NeoFly: nenhum arquivo nos diretórios padrão.")
            messagebox.showinfo("NeoFly não localizado",
                "Não encontrei common.db nem std.bin nas pastas usuais.\n\n"
                "Verifique %PROGRAMDATA%\\NeoFly e %LOCALAPPDATA%\\Programs\\NeoFly; "
                "se instalou por ZIP, procure também na pasta onde extraiu o NeoFly."
            )

    def _analyze(self):
        candidates = discover_neofly_databases()
        src=filedialog.askopenfilename(title="Selecione common.db ou std.bin (feche o NeoFly primeiro)",
                       initialdir=str(candidates[0].parent) if candidates else str(Path.home()),
                       filetypes=[("Dados do NeoFly","*.db *.bin"),("Todos os arquivos","*.*")])
        if not src:
            return
        if not messagebox.askyesno("Inspeção de segurança",
                  "O NeoFly está fechado? A análise copia o arquivo para a pasta do AeroCarreira e não o modifica."):
            return
        try:
            report=inspect_neofly(src,state_dir()/"neofly_analise")
            p=state_dir()/"neofly_analise"/"neofly_schema_report.json"
            self._log(f"NeoFly: formato {report['format']}; {len(report['tables'])} tabelas detectadas.")
            self._log(f"Relatório de esquema salvo: {p}")
            messagebox.showinfo("Análise concluída",f"Formato: {report['format']}\nTabelas: {len(report['tables'])}\n\nRelatório sem registros pessoais:\n{p}\n\nO NeoFly original permanece intocado.")
        except Exception as exc:
            self._log(f"Inspeção interrompida: {exc}")
            messagebox.showerror("Análise interrompida",str(exc))

    def _close(self):
        self._checkpoint(force=True)
        self.bridge.stop()
        if self.sim:
            self.sim.stop()
        self.storage.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
