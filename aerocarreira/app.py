"""Painel Windows Tkinter. O domínio e banco de dados podem ser testados sem GUI."""
from __future__ import annotations
from dataclasses import replace
import json
import os
import subprocess
import sys
from pathlib import Path
from queue import Queue, Empty
from tkinter import Tk, Toplevel, Frame, Label, Button, Entry, StringVar, IntVar, Checkbutton, Canvas, filedialog, messagebox, Text, END
from tkinter import ttk
from time import strftime, localtime, time
from .domain import FlightTracker, Career, MISSIONS, AIRPORTS, distance_nm, Phase, Airport
from .storage import Storage
from .profiles import ProfileManager
from . import pilot_career
from .sim_adapter import SimConnectWorker
from .connection_notices import ReconnectWarningFilter
from .demo import demo_samples
from .neo_inspect import inspect_neofly, discover_neofly_databases
from .pilot import QUALIFICATIONS, qualification_eligibility, flight_xp, level_progress, progress_fraction
from .contracts import (AirportCatalog, TYPES, TYPE_BY_CODE, PLANE_BY_CODE,
                        generate_offers, eligibility, matches_aircraft)
from .employment import (EMPLOYER_BY_CODE, vacancies, weekly_period,
    employment_eligibility, generate_employer_routes, OWN_MIN_LEVEL, OWN_INVESTMENT)
from .flightplan import export_vfr_plan
from .flight_operations import save as save_flight_operations, read_saved as read_flight_operations, validated as validated_flight_operations, to_mission as flight_operations_mission, route_stats as flightops_route_stats, SETTING as FLIGHTOPS_SETTING
from .finance import AIRCRAFT_ECONOMY, brl, estimated_minutes
from .contracts import aircraft_model
from .fuel import FuelManager
from .manifest import mission_manifest
from .msfs_airports import catalog_from_msfs, strict_mission, restricted_mission
from .payload import load_plan, load_confirmed
from .fleet import used_market, resale_price
from .planning import Preflight, inspect_preflight, aircraft_title_matches
from .flight_audit import real_clock_verified, assistance_verified, flight_safety_xp
from .taxi import PostLandingTaxi
from .aircraft_catalog import scan_installed_aircraft, detect_package_roots
from .ingame_bridge import PanelState, LocalPanelServer
from . import __version__, type_ratings, settings_center

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
        self.post_landing_taxi = PostLandingTaxi()
        self.profiles=ProfileManager(state_dir())
        self.settings_prefs=settings_center.read_global(state_dir())
        self.airline_available_codes=set()
        self.airline_scan_count=None
        self.profile_dir=self.profiles.path()
        self.storage=Storage(self.profiles.database())
        self.location_recovered=self.storage.recover_legacy_location()
        self.fuel_manager=FuelManager(self.storage)
        self.pending_fuel_ref=None
        self.dispatch_state={}
        self.weight_bonus_frozen=0
        self.last_resource_warning={}
        self._payload_last_request=0.0
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
                self.post_landing_taxi=PostLandingTaxi.from_snapshot(checkpoint.get('post_landing_taxi_v2'))
                if self.tracker.phase == Phase.AIRBORNE and self.career.mission:
                    self.realism_frozen = float(checkpoint.get('realism_frozen',0.0))
                    self.realism_mission = checkpoint.get('realism_mission')
                self.fuel_company_guard=checkpoint.get('fuel_company_guard')
                self.dispatch_state=checkpoint.get('dispatch_state') or {}
                self.weight_bonus_frozen=int(checkpoint.get('weight_bonus_frozen',0))
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
        self.reconnect_notices=ReconnectWarningFilter()
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
        self.msfs_airports_ready=False
        self.bridge_state = PanelState()
        self.bridge = LocalPanelServer(self.bridge_state, allow_commands=True)
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
        self.dashboard = None
        if os.getenv("FLIGHTSIM_CLASSIC") != "1":
            from .dashboard_controller import DashboardController
            self.dashboard = DashboardController(self)
        if os.getenv('FLIGHTSIM_HEADLESS')!='1':
            # Sem bloquear o Tk: worker se reconecta se o MSFS ainda não abriu.
            self.root.after(700,self._auto_connect)

    def _auto_connect(self):
        if (self.mode=='Desconectado' and self.sim is None
                and self.settings_prefs.get('autoconnect',True)):
            self._connect()

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
        window.title("FlightSim • Piloto e habilitações (virtuais)")
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
        self.sim = SimConnectWorker(self.queue, generation=self.session_generation,
            reconnect=self.settings_prefs.get('reconnect',True))
        self.airport_catalog=None
        self.msfs_airports_ready=False
        if self.dashboard:
            self.dashboard.presenter.market_key=None
            self.dashboard.presenter.offers={}
            self.dashboard.presenter.position_center=None
        self.mode="MSFS"
        self.status_var.set("Conectando ao MSFS...")
        self._log("Iniciando monitoramento com reconexão automática.")
        self.reconnect_notices.reset()
        self.sim.start()

    def _stop(self):
        if self.sim:
            self.sim.stop()
            self.sim = None
        self.session_generation += 1  # descartar mensagens de sessões antigas
        self.connected=False
        self.msfs_airports_ready=False
        self.airport_catalog=None
        self.mode="Desconectado"
        self.status_var.set("Desconectado")

    def _demo_start(self):
        if self.career.mission or self.tracker.phase == Phase.AIRBORNE:
            self._log("Demo bloqueada: há um contrato/voo real pendente. Preserve-o ou cancele o contrato primeiro.")
            return
        self._stop()
        self.tracker.reset()
        self.post_landing_taxi=PostLandingTaxi()
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

    def _accept_specific(self, m, interactive=True):
        def warn(title, message):
            if interactive:
                messagebox.showwarning(title, message)
            else:
                self._ingame_last_error = str(message)
                self._log('INGAME • ' + title + ': ' + str(message))
        m=mission_manifest(m)
        # Em jogo real, catálogo vivo do MSFS é a ÚNICA fonte de aeroportos.
        # Mesmo uma oferta antiga no SQLite NÃO comprova aeroporto instalado.
        if self.mode!='Demo':
            validated=strict_mission(m,self.airport_catalog if self.msfs_airports_ready else None)
            if validated is None:
                self._log('MERCADO BLOQUEADO: origem ou destino não existe na base lida do MSFS desta sessão. Nenhuma rota externa será aceita.')
                self.status_var.set('Aguardando catálogo oficial do MSFS')
                return False
            m=validated
        offline = self.mode == "Desconectado"
        if not offline and (self.mode not in ("MSFS", "Demo") or self.last_sample is None):
            warn("Contrato", "Conecte ao MSFS e aguarde telemetria em solo.")
            return False
        if offline:
            profile=self.storage.get_pilot()
            if profile is None or m.origin != profile['home_icao']:
                warn('Mercado', 'No modo offline só é possível aceitar na base cadastral do piloto.')
                return False
        if self.mode == "Demo" and m.id != "REC-ITA":
            warn("Demo", "A demo fixa simula somente SBRF → SIPE.")
            return False
        if self.mode == "MSFS" and (not self.connected or not self.last_sample.on_ground
                                   or time() - self.last_sample.timestamp > 10):
            warn("Contrato", "Aceite no solo com telemetria atualizada.")
            return False
        if m.category != "legacy":
            if self.storage.get_pilot() is None:
                warn("Contrato", "Cadastre seu piloto primeiro.")
                return False
            allowed, reason = eligibility(m, self.storage.pilot_stats(),
                                          self.storage.owned_qualifications(),
                                          self.storage.family_experience())
            if not allowed:
                warn("Contrato bloqueado", reason)
                return False
            if m.company_code=='OWN':
                from .airline_operations import business_planes
                if self.storage.employment_state()['mode']!='empresario':
                    warn('Contrato','Somente o proprietário pode aceitar rota empresarial.')
                    return False
                # Só uma aeronave empresarial real, na origem, pode executar
                # esse contrato; nenhuma aeronave particular é transferida.
                eligible_planes=[p for p in business_planes(self.storage)
                    if m.id.startswith('OWN-'+str(p['id'])+'-')
                    and p['code']==m.employer_plane and p['airport']==m.origin
                    and p['condition']>=15]
                if not eligible_planes:
                    warn('Contrato','Aeronave empresarial não está disponível nesta origem.')
                    return False
            elif m.company_code and (self.storage.employment_state()['mode']!='empregado' or
                                   self.storage.employment_state()['employer_code']!=m.company_code):
                warn('Contrato', 'Trecho exclusivo da companhia empregadora.')
                return False
            if m.company_code and m.company_code!='OWN':
                if self.mode!='MSFS' or not self.connected or not self.last_sample:
                    warn('Contrato da companhia',
                        'Conecte ao MSFS com a aeronave habilitada antes de aceitar a escala.')
                    return False
                model=m.employer_plane
                company=m.company_code
                ratings=type_ratings.owned(self.storage)
                if not type_ratings.valid_for_company(company,model,ratings):
                    warn('Contrato da companhia',
                        'Modelo não habilitado para esta empregadora. Consulte Treinamento.')
                    return False
                if model not in self.airline_available_codes:
                    warn('Contrato da companhia',
                        'Aeronave não verificada no ambiente MSFS. Abra o modelo ou escaneie a instalação.')
                    return False
                if (self.mode=='MSFS' and self.last_sample and
                        not matches_aircraft(self.last_sample.aircraft_title,model)):
                    warn('Contrato da companhia',
                        'Carregue no MSFS o modelo '+PLANE_BY_CODE[model].name+
                        ' antes de aceitar esta rota.')
                    return False
            if self.storage.contract_completed(m.id):
                warn("Contrato", "Este contrato já foi concluído. Aguarde nova oferta.")
                return False
        try:
            self.career.accept(m, None if offline else self.last_sample)
            self.storage.set_setting('preflight_v1','')  # outro contrato exige novo despacho
            self.dispatch_state={'mission_id':m.id,'route':'pending',
                                 'payload':'waiting_sim','weights':{},
                                 'weight_expected_lbs':None,'message':'Preparação iniciada'}
            self.weight_bonus_frozen=0
            self._show_mission()
            self._checkpoint(force=True)
            self._log(f"Contrato aceito: {m.title} ({m.origin} → {m.destination}).")
            if m.freelance:
                plane = PLANE_BY_CODE[m.employer_plane]
                self._log(f"FREELANCER: avião fornecido pelo contratante: {plane.name}.")
                self._log("Selecione este modelo no MSFS antes de decolar; o addon NÃO muda o avião automaticamente.")
                if not offline and self.last_sample and not matches_aircraft(self.last_sample.aircraft_title, m.employer_plane):
                    self._log(f'FREELANCER: troque para {plane.name} no MSFS; carga ficará pendente até o modelo corresponder.')
            # O clique Aceitar missão já é consentimento explícito: sem novo
            # messagebox, tenta rota e carga, deixando status visível.
            self._prepare_active_plan(automatic=True)
            self._queue_payload_load()
            self._checkpoint(force=True)
            return True
        except ValueError as exc:
            warn("Contrato",str(exc))
            return False

    def _market_window(self):
        if self.market_dialog is not None and self.market_dialog.winfo_exists():
            self.market_dialog.lift()
            return
        if not self.storage.get_pilot():
            messagebox.showwarning("Mercado regional", "Crie seu perfil em 'Meu piloto / Habilitações'.")
            return
        if self.mode!='Demo' and not (self.connected and self.msfs_airports_ready and self.airport_catalog):
            self._log('MERCADO: aguardando inventário de aeroportos do MSFS. Sem catálogo externo.')
            return
        if self.airport_catalog is None:self.airport_catalog=AirportCatalog()  # Demo
        catalog=self.airport_catalog
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
        window.title("FlightSim • Mercado regional e Freelancer")
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
            if (force or self.storage.get_setting('reward_model_version') != '2'
                    or not self.storage.offer_cache_valid(center.icao, now)):
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
                self.storage.set_setting('reward_model_version', '2')
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

    def _prepare_active_plan(self, automatic=False):
        """Exporta plano VFR e solicita importação em solo sem segundo aceite."""
        m=self.career.mission
        if not m:
            if not automatic:messagebox.showinfo('Plano VFR','Aceite primeiro um contrato.')
            return False
        if self.mode!='Demo':
            validated=strict_mission(m,self.airport_catalog if self.msfs_airports_ready else None)
            if validated is None:
                if self.dispatch_state:self.dispatch_state['route']='waiting_navdata'
                self._log('PLANO NÃO ENVIADO: origem/destino ainda não verificados no MSFS; sem coordenadas externas.')
                return False
            m=validated
            self.career.mission=m
        try:
            data=self._saved_preflight()
            # O contrato pode ter uma rota editada e salva; nunca herdar rota livre.
            saved_route = read_flight_operations(self.storage, m)
            stops = []
            if saved_route and saved_route["mode"] == "contract":
                try:
                    valid_route = validated_flight_operations(
                        {k: saved_route[k] for k in
                         ("mode", "origin", "destination", "altitude_ft", "waypoints", "checks")},
                        self._flightops_catalog(), m)
                    stops = valid_route["waypoints"]
                except (KeyError, ValueError, TypeError):
                    stops = []
            path=export_vfr_plan(m,self.profile_dir/'planos_vfr',
                                 data.altitude_ft if data else 2500,waypoints=stops)
            self._log(f'Plano VFR exportado: {path}')
        except (OSError,ValueError) as exc:
            self._log('PLANO VFR: '+str(exc))
            if self.dispatch_state:self.dispatch_state['route']='error'
            if not automatic:messagebox.showerror('Plano VFR',str(exc))
            return False
        if not (self.mode=='MSFS' and self.connected and self.sim and self.last_sample
                and self.last_sample.on_ground and time()-self.last_sample.timestamp<10):
            if self.dispatch_state:self.dispatch_state['route']='waiting_sim'
            self._log('Plano VFR guardado. Carregamento automático pendente: conecte MSFS com avião no solo.')
            return False
        self.sim.request_plan_load(path)
        if self.dispatch_state:self.dispatch_state['route']='loading'
        self._log('Plano VFR enviado ao SimConnect. A API padrão do MSFS 2020 atualiza ATC, não garante o GPS/mapa VFR.')
        return True

    def _queue_payload_load(self):
        m=self.career.mission
        if not m or not self.dispatch_state or self.dispatch_state.get('mission_id')!=m.id:
            return False
        s=self.last_sample
        if not (self.mode=='MSFS' and self.connected and self.sim and s
                and time()-s.timestamp<12 and s.on_ground):
            self.dispatch_state['payload']='waiting_sim'
            return False
        chosen=(m.employer_plane if m.freelance else
                (self.storage.fleet_manager().selected() or {}).get('code'))
        if not chosen or aircraft_model(s.aircraft_title)!=chosen:
            self.dispatch_state.update(payload='waiting_aircraft',
                message='Selecione no MSFS a aeronave do contrato.')
            return False
        try:
            distribution=load_plan(s,m)
        except (ValueError,TypeError) as exc:
            self.dispatch_state.update(payload='waiting_weight',
                message=str(exc))
            return False
        self.sim.request_payload_set(m.id,distribution['stations'])
        self.dispatch_state.update(payload='loading',weights=distribution['stations'],
            weight_expected_lbs=distribution['total_lbs'],
            message='Aplicando carga • aguardando retorno das estações.')
        self._payload_last_request=time()
        self._log(f'CARGA: {m.manifest_label} ({m.payload_kg:.1f} kg) → MSFS. MTOW previsto: {distribution["total_lbs"]:.1f}/{distribution["max_lbs"]:.1f} lb.')
        return True

    def _verify_payload(self,s):
        m=self.career.mission
        if not m or not self.dispatch_state or self.dispatch_state.get('mission_id')!=m.id or not s.on_ground:
            return
        status=self.dispatch_state.get('payload')
        if status=='verified' and s.payload_station_weights:
            if not load_confirmed(s.payload_station_weights,self.dispatch_state.get('weights') or {}):
                self.dispatch_state.update(payload='waiting_weight',
                    message='Peso alterado ao reabrir MSFS; reaplicando manifesto salvo.')
                self._log('CARGA: simulação voltou com pesos diferentes; sincronizando novamente.')
                status='waiting_weight'
        if status=='loading':
            stations=self.dispatch_state.get('weights') or {}
            if (s.payload_station_weights and load_confirmed(s.payload_station_weights,stations)
                and s.total_weight_lbs is not None and s.max_gross_weight_lbs is not None
                and s.total_weight_lbs<=s.max_gross_weight_lbs):
                self.dispatch_state.update(payload='verified',
                    message='Carga confirmada por leitura SimConnect.')
                self._log(f'CARGA CONFIRMADA: {m.manifest_label} • {m.payload_kg:.1f} kg, dentro do MTOW.')
                self._checkpoint(force=True)
            elif time()-self._payload_last_request>18:
                self.dispatch_state.update(payload='waiting_weight',
                    message='Não foi possível confirmar a carga; verifique Peso e Balanceamento.')
        elif status in ('waiting_sim','waiting_aircraft','waiting_weight'):
            if time()-self._payload_last_request>4:
                self._payload_last_request=time()
                self._queue_payload_load()

    def _apply_msfs_catalog(self,raw):
        """Aceita o inventário COMPLETO, produzido pela sessão SimConnect atual."""
        try:
            catalog=catalog_from_msfs(raw)
        except (ValueError,TypeError) as exc:
            self._log('AEROPORTOS MSFS: dados recusados: '+str(exc))
            return
        self.airport_catalog=catalog
        self.msfs_airports_ready=True
        self._log(f'AEROPORTOS MSFS: {len(catalog.locations)} aeródromos confirmados pelo simulador. Catálogos externos ignorados.')
        if self.dashboard:
            presenter=self.dashboard.presenter
            presenter.market_key=None
            presenter.offers={}
            presenter.position_lookup=None
            presenter.position_center=None
            presenter.refresh_market(force=True)
        if self.career.mission:
            verified=strict_mission(self.career.mission,catalog)
            if verified is None:
                self._log('CONTRATO ANTERIOR: aeroporto não encontrado no MSFS; rota e despacho bloqueados. Não foi cancelado automaticamente.')
                if self.dispatch_state:
                    self.dispatch_state.update(route='invalid_airport',
                        message='Origem/destino ausentes da instalação MSFS; contrato legado preservado.')
            else:
                self.career.mission=verified
                if self.dispatch_state.get('route') in ('waiting_navdata','waiting_sim','pending'):
                    self._prepare_active_plan(automatic=True)
                self._checkpoint(force=True)

    def _warn_resources(self,s):
        plane=self.storage.fleet_manager().selected()
        if not plane or self.mode!='MSFS':return
        ref=plane['ref']
        fuel=self.fuel_manager.get(ref)
        ratio=(sum(fuel['tanks'].values())/sum(fuel['capacities'].values())
               if fuel and fuel['capacities'] and sum(fuel['capacities'].values())>0 else None)
        for kind,low,notice in (
            ('fuel',ratio is not None and ratio<=.20,
             'COMBUSTÍVEL BAIXO (≤20%): abasteça antes de voar.'),
            ('wear',plane['condition'] is not None and plane['condition']<=20,
             'DESGASTE CRÍTICO (≤20% de condição): agende manutenção.')):
            key=(ref,kind)
            if low and not self.last_resource_warning.get(key):
                self._log('ALERTA '+ref+': '+notice)
                self.last_resource_warning[key]=True
            elif not low:
                self.last_resource_warning.pop(key,None)

    def _employment_window(self):
        if self.employment_dialog and self.employment_dialog.winfo_exists():
            self.employment_dialog.lift()
            return
        if self.storage.get_pilot() is None:
            messagebox.showwarning('Companhias','Cadastre teu piloto antes de concorrer a vagas.')
            return
        window=Toplevel(self.root)
        self.employment_dialog=window
        window.title('FlightSim • Modalidades de carreira e vagas')
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
        self.label(wrapper,'Opere sua companhia pela nova aba Midnight: caixa empresarial, frota e rotas próprias.',
                   9,MUTED).pack(anchor='w',pady=(8,0))
        redraw()

    def _cancel(self):
        self.career.cancel()
        self.storage.set_setting('preflight_v1','')
        self.dispatch_state={}
        self.weight_bonus_frozen=0
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

    def _checkpoint_data(self, tracker=None, post_landing=None):
        post=self.post_landing_taxi if post_landing is None else post_landing
        return {"version": 1, "career": self.career.snapshot(),
                "tracker": (tracker or self.tracker).snapshot(),
                "post_landing_taxi_v2":post.snapshot(),
                'realism_frozen':self.realism_frozen,
                'realism_mission':self.realism_mission,
                'fuel_penalty_frozen':self.fuel_penalty_frozen,
                'fuel_mode_at_takeoff':self.fuel_mode_at_takeoff,
                'fuel_ref_frozen':self.fuel_ref_frozen,
                'fuel_company_guard':self.fuel_company_guard,
                'dispatch_state':self.dispatch_state,
                'weight_bonus_frozen':self.weight_bonus_frozen}

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
        info = ["FlightSim " + __version__, f"modo={self.mode}",
                f"fase={self.tracker.phase.value}",
                f"missao={self.career.snapshot()}",
                "LOG:", self.log_text.get("1.0", END)]
        path.write_text("\n".join(info), encoding="utf-8")
        self._log(f"Log salvo em {path}")
        messagebox.showinfo("Diagnóstico salvo", f"Arquivo local:\n{path}\n\nPode conter localização do voo; revise antes de compartilhar.")

    def _mark_aircraft_available(self, title):
        code=type_ratings.detect_model(title) or aircraft_model(title)
        if code and code not in self.airline_available_codes:
            self.airline_available_codes.add(code)
            if getattr(self,'dashboard',None):
                self.dashboard.presenter.market_key=None

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
        if status in ('consuming','calibrated') and self.fuel_manager.confirm_pending(ref):
            self.pending_fuel_ref=None
            self._log('ABASTECIMENTO confirmado pelo MSFS e consolidado no save: '+ref)
        if status=='write_not_confirmed' and self.fuel_manager.pending(ref):
            old=self.fuel_manager.rollback_pending(ref)
            self.pending_fuel_ref=None
            self.career.balance=int(self.storage.get_setting('balance') or 0)
            self.balance_var.set(brl(self.career.balance))
            if old and self.sim:self.sim.request_fuel_restore(old)
            self._log('ABASTECIMENTO ESTORNADO: MSFS não confirmou os tanques após tentativas.')
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
        if self.mode=='MSFS' and self.connected:
            self._mark_aircraft_available(s.aircraft_title)
        self.last_sample=s
        self._sync_fuel(s)
        self._verify_payload(s)
        if (self.career.mission and self.dispatch_state.get('mission_id')==self.career.mission.id
                and self.dispatch_state.get('route') in ('waiting_sim','waiting_navdata')
                and s.on_ground and self.mode=='MSFS' and self.connected and self.msfs_airports_ready):
            if (self.dispatch_state['route']=='waiting_sim' or
                    self.career.mission.nav_source=='MSFS'):
                self._prepare_active_plan(automatic=True)
        self._warn_resources(s)
        fmt=lambda n: f"{n:,.0f}"
        for key,val in {
            "ias":fmt(s.ias_kt),"gs":fmt(s.groundspeed_kt) + ("~" if s.groundspeed_estimated else ""),
            "agl":fmt(s.agl_ft),"alt":fmt(s.altitude_ft),
            "vs":f"{s.vs_fpm:+,.0f}",
            "lat":f"{s.latitude:.5f}","lon":f"{s.longitude:.5f}",
            "fuel":f"{s.fuel_gallons:.1f}" if s.fuel_gallons is not None else "—"}.items():
            self.flight_vars[key].set(val)
        if self.mode=='MSFS':
            key=self.post_landing_taxi.observe(s)
            if key:
                try:
                    penalty=self.storage.apply_postflight_taxi_penalty(key)
                    if penalty:
                        self._log(f'TÁXI APÓS POUSO: -{penalty} XP neste voo (pista liberada, excesso sustentado).')
                        self._refresh_pilot_summary()
                    self._checkpoint(force=True)
                except Exception as exc:
                    self._log('Não foi possível registrar táxi após pouso: '+str(exc))
                    self.post_landing_taxi.penalty_marked=False
                    self.post_landing_taxi.phase='taxi'
                    self.post_landing_taxi.fast_since=s.timestamp
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
                self.weight_bonus_frozen=0
                self.fuel_penalty_frozen=(.3 if self.storage.get_setting('fuel_control_enabled')=='0' else 0.0)
                ref,model=self._fuel_ref_for_sample(s)
                self.fuel_ref_frozen=ref
                self.fuel_mode_at_takeoff=bool(self.fuel_penalty_frozen==0 and ref and self.fuel_manager.get(ref))
                if self.fuel_penalty_frozen:
                    self._log('Combustível sob controle do MSFS: penalidade -30% sobre R$ e XP deste voo.')
                plan=self._saved_preflight()
                if (self.career.mission and self.dispatch_state.get('mission_id')==self.career.mission.id
                    and self.dispatch_state.get('payload')=='verified'
                    and s.total_weight_lbs is not None and s.max_gross_weight_lbs is not None
                    and s.total_weight_lbs<=s.max_gross_weight_lbs):
                    self.weight_bonus_frozen=5
                    if plan is None:
                        plan=Preflight(self.career.mission.id,s.aircraft_title or '',
                            payload_checked=True,planned_weight_lbs=s.total_weight_lbs,
                            max_weight_lbs=s.max_gross_weight_lbs)
                    else:
                        plan=replace(plan,payload_checked=True)
                    self._log('PESO DENTRO DO MTOW: +5 XP e bônus de pagamento/XP previsto no despacho.')
                if self.career.mission:
                    # Autoavaliação: só dados SimConnect válidos valem bônus.
                    # Clima ao vivo não pode ser provado por esta API.
                    fresh=self.mode=='MSFS' and self.connected and time()-s.timestamp<10
                    verified=({'clock':real_clock_verified(s),
                               'assists':assistance_verified(s),
                               'fuel':s.fuel_gallons is not None and s.fuel_gallons>=0,
                               'weight':(s.total_weight_lbs is not None and
                                         s.max_gross_weight_lbs is not None and
                                         0<s.total_weight_lbs<=s.max_gross_weight_lbs)}
                              if fresh else {})
                    auto_fraction=.03*int(verified.get('clock') is True)+.03*int(verified.get('assists') is True)
                    if plan and not aircraft_title_matches(plan.aircraft_title,s.aircraft_title):
                        self._log('Despacho: modelo divergente; sem bônus de checklist.')
                        self.realism_frozen=round(auto_fraction,4)
                        self.realism_mission=self.career.mission.id
                    elif plan:
                        try:
                            snapshot=replace(plan,planned_fuel_gal=s.fuel_gallons,
                                planned_weight_lbs=s.total_weight_lbs,
                                max_weight_lbs=s.max_gross_weight_lbs)
                            details=inspect_preflight(self.career.mission,snapshot,verified=verified)
                            self.realism_frozen=details['bonus_fraction']
                            self.realism_mission=self.career.mission.id
                        except ValueError as exc:
                            self._log('Despacho indisponível: '+str(exc))
                    else:
                        automatic=Preflight(self.career.mission.id,s.aircraft_title or '',
                            planned_fuel_gal=s.fuel_gallons,
                            planned_weight_lbs=s.total_weight_lbs,
                            max_weight_lbs=s.max_gross_weight_lbs)
                        self.realism_frozen=inspect_preflight(
                            self.career.mission,automatic,verified=verified)['bonus_fraction']
                        self.realism_mission=self.career.mission.id
                    self._log(f'Realismo confirmado pelo MSFS/checklist: +{self.realism_frozen*100:.1f}% de XP e pagamento.')
                    if verified.get('clock') is None:self._log('Horário UTC: telemetria indisponível, sem bônus automático.')
                    if verified.get('assists') is None:self._log('Assistências: telemetria incompleta, sem bônus automático.')
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
                next_post=PostLandingTaxi.begin(start,s) if self.mode=='MSFS' else PostLandingTaxi()
                checkpoint_after = self._checkpoint_data(tracker=next_tracker,post_landing=next_post)
                checkpoint_after['realism_frozen']=0.0
                checkpoint_after['realism_mission']=None
                checkpoint_after['weight_bonus_frozen']=0
                checkpoint_after['dispatch_state']={}
                checkpoint_after['fuel_penalty_frozen']=0.0
                checkpoint_after['fuel_mode_at_takeoff']=False
                checkpoint_after['fuel_ref_frozen']=None
                realism_fraction=(self.realism_frozen if payment and
                                  self.realism_mission==payment['mission'] else 0.0)
                safety_xp=flight_safety_xp(self.tracker,v)
                if self.mode=='Demo':safety_xp=0  # demo nunca dá bônus/penalidade por procedimento
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
                                        fuel_prepaid=self.fuel_mode_at_takeoff,
                                        flight_xp_extra=safety_xp,
                                        flight_xp_weight_bonus=(self.weight_bonus_frozen if payment else 0),
                                        verified_msfs=self.mode=='MSFS' and self.connected)
                except Exception as exc:
                    self._log(f"FALHA AO SALVAR pouso: {exc}. Não feche antes de exportar log.")
                    self.status_var.set("Erro ao salvar voo")
                    self.career.restore(old_career_state)
                    self.career.balance = old_balance
                    # O checkpoint anterior mantém a fase em voo; ao reiniciar,
                    # o app poderá confirmar novamente o pouso em solo.
                    return
                self.tracker = next_tracker
                self.post_landing_taxi=next_post
                self.realism_frozen=0.0
                self.realism_mission=None
                self.weight_bonus_frozen=0
                self.dispatch_state={}
                self.fuel_penalty_frozen=0.0
                self.fuel_mode_at_takeoff=False
                self.fuel_ref_frozen=None
                self.career.balance = int(self.storage.get_setting("balance") or 0)
                summary = self.storage.flight_finance(start)
                actual_credit = self.career.balance - old_balance
                if inserted:
                    if getattr(self,'dashboard',None):
                        self.dashboard.presenter.market_key=None
                        self.dashboard.presenter.pilot_career_cache=None
                    if self.mode=='MSFS' and self.connected:
                        self._mark_aircraft_available(s.aircraft_title)
                if inserted and self.storage.get_pilot() is not None:
                    base_xp=flight_xp(payment['reward'] if payment else 0)
                    bonus_xp=round(base_xp*realism_fraction) if payment else 0
                    # valor congelado antes de limpar o estado
                    earned=self.storage.conn.execute('SELECT xp FROM pilot_xp_ledger WHERE flight_key=?',
                        (f"takeoff:{float(start['timestamp']):.6f}:{float(start['lat']):.7f}:{float(start['lon']):.7f}",)).fetchone()
                    self._log(f"PROGRESSO DO PILOTO: +{earned[0] if earned else 0} XP ({bonus_xp} do despacho, {safety_xp:+d} de segurança).")
                    if v is not None:self._log(f'Toque estimado: {v:+.0f} ft/min; arremetidas: {e.get("go_arounds",0)}; toque-e-arremetidas: {e.get("touch_and_go",0)}.')
                    self._refresh_pilot_summary()
                if not inserted:
                    self._log("Pouso já salvo anteriormente: pagamento duplicado bloqueado.")
                    saved = self.storage.get_checkpoint()
                    if saved:
                        self.career.restore(saved.get("career", {}))
                elif payment and payment['mission'].startswith('EMP-'):
                    self._log('VOO DA EMPREGADORA: não paga R$ nem XP imediato; contabilizado na meta semanal.')
                elif payment and payment['mission'].startswith('OWN-'):
                    self._log('VOO EMPRESARIAL: receita e custos lançados somente no caixa da companhia.')
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
                self._log("ESTOL: aviso registrado; poderá reduzir XP deste voo após o pouso.")
            elif e["type"] == "go_around":
                self._log("ARREMETIDA detectada: sem penalidade; bônus de pouso suave cancelado neste voo.")
            elif e["type"] == "touch_and_go":
                self._log("TOQUE E ARREMETIDA detectado: voo continua, sem pagamento ou encerramento antecipado.")
            elif e["type"] == "hard_maneuver":
                self._log("MANOBRA BRUSCA: força G extrema sustentada; evento contabilizado.")
        if previous_phase != self.tracker.phase or self.career.mission and events:
            self._checkpoint(force=True)
        else:
            self._checkpoint()

    def _execute_ingame_command(self, action, value, request_id=None):
        """Run the toolbar request on the existing Tk/SQLite/SimConnect owner thread.

        The browser is never trusted to supply a price, a reward or a flight
        state. Returning True means the motor accepted the action; asynchronous
        SimConnect writes must still be verified from subsequent samples.
        """
        if action == 'market_refresh':
            if not self.dashboard:
                return False, 'Mercado ainda não inicializado.'
            self.dashboard.presenter.refresh_market(force=True)
            self._ingame_offers_next = 0
            return True, 'Ofertas atualizadas pelo motor.'

        # Six operational pages all reuse the original Tk thread, database and
        # domain rules. No money, runway or XP values are trusted from the iframe.
        # Read-only/exports and note editing do not require an aircraft on ground.
        if action == 'logbook_note':
            from . import flight_history
            flight_history.save_note(self.storage,value['flight_id'],value['note'])
            if self.dashboard:self.dashboard.presenter.history_cache=None
            self._ingame_office_next=0
            return True, 'Anotação salva no Logbook.'

        if action in ('plan_export','plan_send'):
            try:
                message=self._flightops_export(send=action=='plan_send')
                self._ingame_office_next=0
                return True, message if action=='plan_send' else 'Plano .PLN exportado para a pasta da carreira.'
            except (ValueError,TypeError,KeyError,OSError) as exc:
                return False, str(exc)

        s = self.last_sample
        if not (self.mode == 'MSFS' and self.connected and self.sim and s
                and time() - s.timestamp < 10 and s.on_ground
                and self.tracker.phase != Phase.AIRBORNE):
            return False, 'Ação disponível somente com MSFS conectado e aeronave em solo.'

        if action in ('plan_save','plan_clear'):
            try:
                message=(self._flightops_save(value) if action=='plan_save'
                         else self._flightops_clear())
                self._ingame_office_next=0
                return True,message
            except (ValueError,TypeError,KeyError,OSError) as exc:
                return False, str(exc)

        if action in ('fleet_select','fleet_service','fleet_buy_new','fleet_buy_used',
                      'fleet_rent','fleet_sell','fleet_insurance'):
            from .aircraft_marketplace import execute_market, market_location
            if self.career.mission:
                return False,'Finalize ou cancele o contrato antes de alterar a frota.'
            fm=self.storage.fleet_manager()
            ref=value
            if action in ('fleet_select','fleet_service','fleet_insurance'):
                if action=='fleet_insurance':
                    if '|' not in value:return False,'Formato de seguro inválido.'
                    ref,flag=value.rsplit('|',1)
                    if flag not in ('0','1'):return False,'Opção de seguro inválida.'
                plane=fm.get(ref)
                if not plane:
                    return False,'Aeronave não está no hangar ou aluguel expirou.'
                if action=='fleet_select':
                    fm.select(ref)
                    self._ingame_office_next=0
                    return True,'Aeronave selecionada: '+plane['title']+'. A troca no MSFS continua manual.'
                airport,reason=market_location(self,self.dashboard.presenter.center if self.dashboard else None)
                if not airport or plane['airport'] != airport:
                    return False,reason or 'Revisão exige o aeroporto de localização do avião.'
                if action=='fleet_insurance':
                    import uuid
                    tx=str(uuid.uuid5(uuid.NAMESPACE_URL,'flightsim-insurance:'+str(request_id)))
                    fm.set_insurance(ref,flag=='1',request_id=tx)
                    self.career.balance=int(self.storage.get_setting('balance') or 0)
                    self.balance_var.set(brl(self.career.balance))
                    self._ingame_office_next=0
                    return True,('Seguro ativado.' if flag=='1' else 'Seguro desativado.')+' Saldo '+brl(self.career.balance)
                if action=='fleet_service':
                    if ref.startswith('legacy:'):
                        self.storage.service_aircraft(plane['code'])
                        cost='Revisão legada concluída.'
                    else:
                        cost='Revisão concluída por '+brl(fm.service(ref))+'.'
                    self.career.balance=int(self.storage.get_setting('balance') or 0)
                    self.balance_var.set(brl(self.career.balance))
                    self._ingame_office_next=0
                    return True,cost
            mapping={'fleet_buy_new':'aircraft_buy_new','fleet_buy_used':'aircraft_buy_used',
                     'fleet_rent':'aircraft_rent','fleet_sell':'aircraft_sell'}
            # The persisted fleet_requests row prevents double charges even
            # if an identical operation reaches a new bridge session.
            import uuid
            financial_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'flightsim-ingame:'+str(request_id)))
            payload=value+'|'+financial_id
            msg=execute_market(self,self.dashboard.presenter.center if self.dashboard else None,
                               mapping[action],payload)
            self._ingame_office_next=0
            return True,msg

        if action in ('finance_loan','finance_repay','finance_tax'):
            if action=='finance_tax':
                self.storage.set_setting('income_tax_enabled','1' if value else '0')
                msg='Imposto virtual de 4% '+('ativado.' if value else 'desativado.')
            else:
                import uuid
                financial_id=str(uuid.uuid5(uuid.NAMESPACE_URL,
                                             'flightsim-ingame-finance:'+str(request_id)))
                if action=='finance_loan':
                    self.storage.take_loan(value,request_id=financial_id)
                    msg='Empréstimo contratado com sucesso.'
                else:
                    self.storage.repay_loan(value,request_id=financial_id)
                    msg='Parcela quitada com sucesso.'
            self.career.balance=int(self.storage.get_setting('balance') or 0)
            self.balance_var.set(brl(self.career.balance))
            self._ingame_office_next=0
            return True,msg+' Saldo '+brl(self.career.balance)+'.'

        if action=='pilot_license_claim':
            granted=self.storage.earn_qualification(value)
            self._ingame_office_next=0
            return True,('Licença '+value+' conquistada.' if granted else 'Licença já registrada.')

        if action.startswith('airline_'):
            if self.career.mission:
                return False,'Finalize ou cancele o contrato antes de alterar a companhia.'
            pilot=self.storage.get_pilot()
            if not pilot:
                return False,'Cadastre primeiro seu piloto.'
            if action=='airline_apply':
                if '|' not in value:return False,'Escolha a vaga e o compromisso.'
                vacancy_id,tier=value.rsplit('|',1)
                if tier not in ('0','10','20'):
                    return False,'Compromisso semanal inválido.'
                region=(self.dashboard.presenter.center.icao
                        if self.dashboard and self.dashboard.presenter.center else pilot['home_icao'])
                vacancy=next((v for v in vacancies(weekly_period(time()),region)
                              if v.id==vacancy_id),None)
                if not vacancy:return False,'Vaga expirada ou não encontrada.'
                self.storage.apply_vacancy(vacancy,time(),int(tier))
                msg='Candidatura enviada; a seleção é semanal.'
            elif action=='airline_review':
                results=self.storage.review_applications(time())
                paid=self.storage.airline_payroll(time())
                msg='Seleção: '+str(len(results))+' resultado(s); folha: '+str(len(paid))+' pagamento(s).'
            elif action=='airline_resign':
                self.storage.resign_employment(time())
                msg='Vínculo encerrado. Histórico preservado.'
            elif action=='airline_found':
                result=self.storage.found_company(value,time())
                msg='Companhia '+result['owner_company']+' fundada.'
            elif action=='airline_buy_plane':
                self.storage.company_buy_plane(value)
                msg='Aeronave incorporada à companhia.'
            else:
                return False,'Comando de companhia não suportado.'
            self.career.balance=int(self.storage.get_setting('balance') or 0)
            self.balance_var.set(brl(self.career.balance))
            if self.dashboard:self.dashboard.presenter.refresh_market(force=True)
            self._ingame_office_next=0
            return True,msg

        if action == 'offer_accept':
            if self.career.mission:
                return False, 'Finalize ou cancele o contrato atual antes de aceitar outro.'
            if not self.dashboard or not self.msfs_airports_ready:
                return False, 'Aguardando catálogo de aeroportos confirmado pelo MSFS.'
            presenter = self.dashboard.presenter
            presenter.refresh_market()
            offer = presenter.offers.get(value)
            if offer is None or self.storage.contract_completed(value):
                return False, 'Oferta não está mais disponível. Atualize o mercado.'
            if not self.storage.get_pilot():
                return False, 'Cadastre um piloto no FlightSim antes de aceitar missões.'
            allowed, reason = eligibility(offer, self.storage.pilot_stats(),
                                          self.storage.owned_qualifications(),
                                          self.storage.family_experience())
            if not allowed:
                return False, reason
            self._ingame_last_error = None
            ok = self._accept_specific(offer, interactive=False)
            if ok:
                self._ingame_offers_next = 0
            return (True, 'Contrato aceito; despacho iniciado pelo motor.') if ok else (
                False, self._ingame_last_error or 'Contrato recusado pelo motor; confira o registro do FlightSim.')

        m = self.career.mission
        if action in ('mission_cancel', 'dispatch_prepare'):
            if not m or value != m.id:
                return False, 'Missão alterada ou inexistente. Atualize o painel.'
            if action == 'mission_cancel':
                self._cancel()
                self._ingame_offers_next = 0
                return True, 'Contrato cancelado sem pagamento.'
            plan = self._prepare_active_plan(automatic=True)
            payload = self._queue_payload_load()
            self._checkpoint(force=True)
            if plan or payload:
                return True, 'Plano/carga enviados; aguarde confirmação do SimConnect.'
            return False, 'Despacho pendente. Confira aeronave, peso e catálogo MSFS.'

        if action == 'fuel_toggle':
            self.storage.set_setting('fuel_control_enabled', '1' if value else '0')
            self._log('INGAME: controle de combustível ' + ('ativado.' if value else 'desativado.'))
            return True, ('Controle de combustível ativado.' if value else
                          'Controle desativado: -30% em dinheiro e XP nos próximos voos.')

        if action == 'fuel_refuel':
            if not self.dashboard:
                return False, 'Controle de frota indisponível.'
            plane = self.storage.fleet_manager().selected()
            if not plane:
                return False, 'Selecione uma aeronave própria no Hangar.'
            if self.career.mission and self.career.mission.freelance:
                return False, 'Não é possível abastecer o avião do contratante.'
            if aircraft_model(s.aircraft_title) != plane['code']:
                return False, 'O avião conectado não corresponde ao selecionado no Hangar.'
            try:
                previous = self.fuel_manager.get(plane['ref'])
                if previous and s.total_weight_lbs is not None and s.max_gross_weight_lbs is not None:
                    from .finance import LITERS_PER_GALLON
                    current_liters = sum(previous['tanks'].values()) * LITERS_PER_GALLON
                    projected = s.total_weight_lbs + (value - current_liters) * 1.58733
                    if projected > s.max_gross_weight_lbs - 1:
                        raise ValueError('Combustível ultrapassaria o MTOW.')
                result = self.fuel_manager.change_liters(plane['ref'], value)
            except (ValueError, TypeError, KeyError) as exc:
                return False, str(exc)
            self.pending_fuel_ref = plane['ref']
            self.sim.request_fuel_restore(result['tanks'])
            self.career.balance = int(self.storage.get_setting('balance') or 0)
            self.balance_var.set(brl(self.career.balance))
            self._log('INGAME: abastecimento de %.1f L enviado ao MSFS. Aguardando leitura.' %
                      result['target_liters'])
            return True, ('Solicitação enviada ao MSFS (%s). Aguardando leitura dos tanques.' %
                          brl(result['cost_brl']))

        return False, 'Comando não suportado.'

    def _publish_bridge(self):
        """Publish sanitized data on the Tk thread; never expose SQLite or financial write access to JS."""
        m = self.career.mission
        now = time()
        sample = self.last_sample if self.connected else None
        s = sample if (sample and now - sample.timestamp < 10) else None
        mission = None
        remaining = None
        if m:
            verified = restricted_mission(
                m, self.airport_catalog if self.msfs_airports_ready else None
            )
            mission = {
                'id': m.id, 'origin': m.origin, 'destination': m.destination,
                'title': m.title, 'reward': m.reward,
                'origin_lat': verified.origin_lat,
                'origin_lon': verified.origin_lon,
                'destination_lat': verified.destination_lat,
                'destination_lon': verified.destination_lon,
                'nav_source': verified.nav_source,
            }
            if s and verified.destination_lat is not None and verified.destination_lon is not None:
                remaining = round(distance_nm(
                    s.latitude, s.longitude,
                    verified.destination_lat, verified.destination_lon
                ), 1)

        # SimConnect sends optional readings that may be absent. Never substitute
        # predicted flight data for missing actual telemetry.
        from math import isfinite
        def number(value, decimals=1):
            return round(value, decimals) if (
                isinstance(value, (float, int)) and not isinstance(value, bool)
                and isfinite(value)
            ) else None

        telemetry = ({
            'ias_kt': number(s.ias_kt), 'gs_kt': number(s.groundspeed_kt),
            'altitude_ft': number(s.altitude_ft, 0),
            'agl_ft': number(s.agl_ft, 0), 'vs_fpm': number(s.vs_fpm, 0),
            'heading_deg': number(s.heading_true_deg),
            'on_ground': bool(s.on_ground),
        } if s else None)
        status = ('connected' if s else
                  'reconnecting' if self.mode == 'MSFS' else 'offline')
        if now >= getattr(self, '_ingame_offers_next', 0):
            offers = []
            presenter = self.dashboard.presenter if self.dashboard else None
            if presenter and self.storage.get_pilot() and self.msfs_airports_ready:
                selected = self.storage.fleet_manager().selected()
                stats = self.storage.pilot_stats()
                for item in list(presenter.offers.values())[:30]:
                    allowed, reason = eligibility(item, stats,
                        self.storage.owned_qualifications(), self.storage.family_experience())
                    from .dashboard import mission_data
                    data = mission_data(item, selected['code'] if selected else None)
                    offers.append({key: data.get(key) for key in
                        ('id','origin','destination','title','category','reward',
                         'distance','minutes','freelance','manifest_label','employer_plane')})
                    offers[-1].update(allowed=bool(allowed),reason=str(reason)[:180])
            self._ingame_offers_cache = offers
            self._ingame_offers_next = now + 1.5
        fuel_info = None
        selected = self.storage.fleet_manager().selected()
        if selected:
            inventory = self.fuel_manager.get(selected['ref'])
            if inventory and inventory.get('capacities'):
                from .finance import LITERS_PER_GALLON
                fuel_info = {'aircraft': selected['title'],
                    'current_liters': number(sum(inventory['tanks'].values()) * LITERS_PER_GALLON),
                    'capacity_liters': number(sum(inventory['capacities'].values()) * LITERS_PER_GALLON)}
        # Office data updates slowly compared with telemetry. Reuse the
        # already tested desktop presenter; never query SQLite in HTTP threads.
        if now >= getattr(self,'_ingame_office_next',0):
            try:
                from .ingame_office import project
                if self.dashboard:
                    self._ingame_office_cache=project(self.dashboard.presenter.snapshot())
                    self._ingame_office_updated=now
                    self._ingame_office_next=now+4
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                self._ingame_office_next=now+4
                self._log('INGAME OFFICE: atualização não disponível: '+str(exc))
        self.bridge_state.update(
            office=getattr(self,'_ingame_office_cache',{}),
            office_updated=getattr(self,'_ingame_office_updated',0),
            offers=getattr(self, '_ingame_offers_cache', []),
            market_ready=bool(self.msfs_airports_ready),
            fuel_control_enabled=self.storage.get_setting('fuel_control_enabled') == '1',
            fuel_inventory=fuel_info,
            dispatch=dict(self.dispatch_state),
            status=status, mode=self.mode, phase=self.tracker.phase.value,
            balance=int(self.career.balance), aircraft=s.aircraft_title if s else None,
            position={'lat': number(s.latitude, 6), 'lon': number(s.longitude, 6)} if s else None,
            fuel_gallons=number(s.fuel_gallons) if s else None,
            mission=mission, telemetry=telemetry,
            remaining_nm=remaining, updated=now,
        )

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
                    self.reconnect_notices.reset()
                    self._log(item)
                elif kind=="error":
                    self.connected=False
                    self.status_var.set("Adaptador indisponível")
                    self._log(item)
                elif kind=="warning":
                    self.status_var.set("Monitorando / recuperação")
                    if self.reconnect_notices.should_log(item):
                        self._log(item)
                elif kind in ('plan_atc_sent','plan_loaded'):
                    if self.dispatch_state:
                        self.dispatch_state.update(route='atc_sent',message=
                            'ATC recebeu comando. GPS/mapa VFR não são sincronizados automaticamente pelo SimConnect MSFS 2020.')
                    self._log(item)
                elif kind=='fuel_sent':
                    self._log('Combustível: solicitação enviada ao MSFS; leitura posterior confirmará.')
                elif kind=='fuel_error':
                    if self.pending_fuel_ref:
                        old=self.fuel_manager.rollback_pending(self.pending_fuel_ref)
                        self.pending_fuel_ref=None
                        self.career.balance=int(self.storage.get_setting('balance') or 0)
                        self.balance_var.set(brl(self.career.balance))
                        self._log('ABASTECIMENTO ESTORNADO: '+item)
                        if old and self.sim:self.sim.request_fuel_restore(old)
                    else:self._log('ALERTA combustível: escrita recusada: '+item)
                elif kind=='plan_error':
                    if self.dispatch_state:self.dispatch_state['route']='error'
                    self._log('PLANO VFR: '+item)
                elif kind=='payload_sent':
                    self._log('Peso enviado ao simulador; aguardando leitura de confirmação.')
                elif kind=='airport_catalog':
                    self._apply_msfs_catalog(item)
                elif kind=='airport_catalog_error':
                    self.msfs_airports_ready=False
                    self.airport_catalog=None
                    if self.dashboard:
                        self.dashboard.presenter.offers={}
                        self.dashboard.presenter.center=None
                    self._log('AEROPORTOS MSFS INDISPONÍVEIS: '+str(item))
                elif kind=='payload_error':
                    if self.dispatch_state:
                        self.dispatch_state.update(payload='error',message=item)
                    self._log('CARGA: '+item)
                elif kind=="disconnected":
                    self.connected=False
                    self.msfs_airports_ready=False
                    self.airport_catalog=None
                    if self.dashboard:
                        self.dashboard.presenter.market_key=None
                        self.dashboard.presenter.offers={}
                        self.dashboard.presenter.center=None
                    self.status_var.set(item)
        except Empty:
            pass
        # Run InGame commands on the same Tk owner thread as desktop commands.
        for _ in range(8):
            try: request_id, action, value = self.bridge.commands.get_nowait()
            except Empty: break
            try:
                ok, message = self._execute_ingame_command(action, value, request_id)
            except Exception as exc:
                self._log('INGAME: falha no comando ' + action + ': ' + str(exc))
                ok, message = False, 'Operação falhou no motor. Consulte o registro.'
            self.bridge.finish_command(request_id, ok, message)
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
        window.title("FlightSim • Finanças, frota e manutenção")
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
        if not getattr(self,'dashboard',None) or self.dashboard.fallback:
            fuel_opts=Frame(main,bg=BG);fuel_opts.pack(fill='x',pady=(5,0))
            fuel_var=IntVar(value=int(self.storage.get_setting('fuel_control_enabled') or '0'))
            def change_fuel_mode():
                if self.tracker.phase==Phase.AIRBORNE:
                    messagebox.showwarning('Combustível','Altere apenas em solo; o modo fica congelado na decolagem.',parent=window)
                    fuel_var.set(int(self.storage.get_setting('fuel_control_enabled') or '0'))
                    return
                self.storage.set_setting('fuel_control_enabled',str(int(fuel_var.get())))
                self._log('Controle combustível '+('ATIVO' if fuel_var.get() else 'DESLIGADO: -30% R$/XP nos próximos voos'))
            Checkbutton(fuel_opts,text='Combustível controlado pelo FlightSim',variable=fuel_var,
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

    def _flightops_catalog(self):
        """Somente aeroportos da sessão confirmada, sem fallback externo no MSFS."""
        if self.mode != "Demo" and not self.msfs_airports_ready:
            raise ValueError("Catálogo de aeroportos do MSFS ainda não verificado.")
        if self.airport_catalog is None:
            raise ValueError("Aguardando aeroportos da sessão.")
        return self.airport_catalog

    def _flightops_read_valid(self):
        catalog = self._flightops_catalog()
        stored = read_flight_operations(self.storage, self.career.mission)
        if not stored:
            raise ValueError("Salve um planejamento válido antes da operação.")
        draft = {k: stored[k] for k in
                 ("mode", "origin", "destination", "altitude_ft", "waypoints", "checks")}
        return validated_flight_operations(draft, catalog, self.career.mission)

    def _flightops_preview(self, data):
        """Projeção autoritativa, sem SQLite, sem dispatch e sem alterar plano salvo."""
        catalog=self._flightops_catalog()
        plan=validated_flight_operations(data,catalog,self.career.mission)
        s=self.last_sample
        live=(self.mode=='MSFS' and self.connected and s is not None and
              time()-s.timestamp<10)
        selected=self.storage.fleet_manager().selected()
        aircraft=(selected['title'] if selected else
                  (s.aircraft_title if live else None))
        return flightops_route_stats(
            plan,catalog,aircraft,
            s.fuel_gallons if live else None,s if live else None)

    def _flightops_save(self, data):
        if self.tracker.phase == Phase.AIRBORNE:
            raise ValueError("Planejamento e checklist ficam congelados após decolar.")
        plan = save_flight_operations(self.storage, data, self._flightops_catalog(), self.career.mission)
        # Bônus só pertence a contratos aceitos: voo livre nunca cria recompensa.
        if plan["mode"] == "contract":
            m = self.career.mission
            s = self.last_sample
            live = bool(self.mode == "MSFS" and self.connected and s and
                        time() - s.timestamp < 10 and s.on_ground)
            if m.freelance:
                assigned = PLANE_BY_CODE.get(m.employer_plane)
                title = assigned.name if assigned else ""
            else:
                active = self.storage.fleet_manager().selected()
                title = active["title"] if active else (s.aircraft_title if live else "")
            route = flightops_route_stats(plan, self.airport_catalog, title)
            preflight = Preflight(
                mission_id=m.id, aircraft_title=title or "",
                altitude_ft=plan["altitude_ft"],
                planned_distance_nm=route["distance_nm"], **plan["checks"],
                planned_fuel_gal=s.fuel_gallons if live else None,
                planned_weight_lbs=s.total_weight_lbs if live else None,
                max_weight_lbs=s.max_gross_weight_lbs if live else None)
            self.storage.set_setting("preflight_v1",
                json.dumps(preflight.snapshot(), ensure_ascii=False))
        self._checkpoint(force=True)
        self._log(f"FLIGHT OPS: planejamento {plan['mode']} salvo: {plan['origin']} → {plan['destination']}.")
        return "Planejamento e checklist salvos. Revalidação automática na decolagem."

    def _flightops_clear(self):
        if self.tracker.phase == Phase.AIRBORNE:
            raise ValueError("Não limpe o plano durante o voo.")
        self.storage.set_setting(FLIGHTOPS_SETTING,"")
        if self.career.mission:
            self.storage.set_setting("preflight_v1","")
            if self.dispatch_state.get("mission_id")==self.career.mission.id:
                self.dispatch_state["route"]="pending"
        self._checkpoint(force=True)
        self._log("FLIGHT OPS: rascunho apagado; contrato, caixa e voos preservados.")
        return "Plano limpo. Contrato e registros preservados."

    def _flightops_export(self, *, send=False):
        plan = self._flightops_read_valid()
        mission = flight_operations_mission(plan, self.airport_catalog, self.career.mission)
        path = export_vfr_plan(mission, self.profile_dir/"planos_vfr",
                              plan["altitude_ft"], waypoints=plan["waypoints"])
        if not send:
            self._log("FLIGHT OPS: plano .PLN exportado: "+str(path))
            return "Arquivo .PLN exportado em "+str(path)
        s = self.last_sample
        if not (self.mode == "MSFS" and self.connected and s and
                time() - s.timestamp < 10 and s.on_ground):
            raise ValueError("Envio exige MSFS conectado, telemetria recente e aeronave em solo.")
        self.sim.request_plan_load(path)
        if plan["mode"] == "contract" and self.dispatch_state.get("mission_id") == mission.id:
            self.dispatch_state["route"] = "loading"
            self._queue_payload_load()
        self._checkpoint(force=True)
        self._log("FLIGHT OPS: .PLN enviado ao SimConnect; não confirma GPS/mapa VFR.")
        return "Plano enviado ao SimConnect (ATC). GPS/mapa VFR não confirmados."

    def _planning_window(self):
        if not self.career.mission:
            messagebox.showinfo('Despacho','Aceite primeiro um contrato regional ou freelancer.')
            return
        if self.planning_dialog is not None and self.planning_dialog.winfo_exists():
            self.planning_dialog.lift();return
        m=self.career.mission
        window=Toplevel(self.root)
        self.planning_dialog=window
        window.title('FlightSim • Despacho pré-voo')
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
        items=[('runway_checked','Pista e iluminação revisadas (declaração manual)'),
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
                    self._log(f'Despacho salvo para {m.origin} → {m.destination}; componentes automáticos serão verificados na decolagem.')
                report.delete('1.0',END)
                report.insert(END,f'Distância: {details["distance_nm"]} NM\nDuração estimada: {details["minutes"]} min\n')
                report.insert(END,f'Combustível mínimo estimado (inclui margem): {details["fuel_required_gal"]} gal\n')
                for key,val in details['components'].items():
                    report.insert(END,f'{"OK" if val["ok"] else "PENDENTE"}: {key} (+{val["rate"]*100:g}%)\n')
                report.insert(END,f'\nBônus previsto: +{details["bonus_fraction"]*100:.1f}% sobre pagamento e XP do contrato\n')
                report.insert(END,'Relógio UTC e assistência de voo: pontuados automaticamente apenas se o MSFS fornecer dados válidos.\n')
                report.insert(END,'Pista/rota são declarações revisadas pelo piloto, não sensores de aeroporto.\n')
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
        window.title('FlightSim • Frota 2.0 e aeronaves do MSFS')
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
        win=Toplevel(self.root);win.title('FlightSim • Aeronaves instaladas MSFS 2020')
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

    def _profile_create(self,payload):
        if not isinstance(payload,dict) or set(payload)!={'name','callsign','home_icao','test_admin'}:
            raise ValueError('Dados de perfil inválidos.')
        entry=self.profiles.create(payload['name'],payload['callsign'],
                                   payload['home_icao'],test_admin=payload['test_admin'])
        self._log('PERFIS: '+entry['name']+' criado em banco separado.')
        return 'Perfil '+entry['name']+' criado. Selecione-o para entrar.'

    def _profile_update(self,payload):
        if not isinstance(payload,dict) or set(payload)!={'name','callsign','home_icao'}:
            raise ValueError('Dados de cadastro inválidos.')
        if self.storage.get_pilot() is None:
            raise ValueError('Cadastre o piloto antes de editar.')
        updated=self.storage.update_pilot(payload['name'],payload['callsign'],payload['home_icao'])
        self.profiles.update_active(**{k:updated[k] for k in ('name','callsign','home_icao')})
        self._refresh_pilot_summary()
        return 'Identificação atualizada, carreira preservada.'

    def _relaunch_profile(self,target=None,reset=False):
        if self.tracker.phase==Phase.AIRBORNE or self.connected:
            raise ValueError('Desconecte o MSFS e termine o voo antes de trocar ou reiniciar o perfil.')
        selected=self.profiles.active()['id']
        if reset and self.profiles.active()['kind']!='test':
            raise ValueError('Reset disponível exclusivamente para perfis Teste.')
        if not reset and not self.profiles.get(target):
            raise ValueError('Perfil inexistente.')
        if not reset and target==selected:
            return 'Este perfil já está ativo.'
        self._checkpoint(force=True)
        if not reset:self.profiles.switch(target)
        self._close()
        if reset:self.profiles.reset_test(selected)
        args=([sys.executable,*sys.argv[1:]] if getattr(sys,'frozen',False)
              else [sys.executable,'-m','aerocarreira'])
        subprocess.Popen(args,close_fds=True)
        return 'Reiniciando no perfil selecionado.'

    def _pilot_showcase(self,payload):
        return pilot_career.set_showcase(self.storage,self.profiles.active(),payload)

    def _pilot_equip(self,code):
        current=pilot_career.snapshot(self.storage,self.profiles.active())
        active={b['code'] for b in current['medals'] if b['status']=='earned'}
        return pilot_career.equip(self.storage,self.profiles.active(),code,active)

    def _close(self):
        if getattr(self,"_closing",False):return
        self._checkpoint(force=True)
        self._closing=True
        if getattr(self,"dashboard",None):self.dashboard.stop()
        self.bridge.stop()
        if self.sim:
            self.sim.stop()
        self.storage.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
