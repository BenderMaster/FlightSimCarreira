"""Painel Windows Tkinter. O domínio e banco de dados podem ser testados sem GUI."""
from __future__ import annotations
import json
import os
from pathlib import Path
from queue import Queue, Empty
from tkinter import Tk, Toplevel, Frame, Label, Button, Entry, StringVar, filedialog, messagebox, Text, END
from tkinter import ttk
from time import strftime, localtime, time
from .domain import FlightTracker, Career, MISSIONS, AIRPORTS, distance_nm, Phase
from .storage import Storage
from .sim_adapter import SimConnectWorker
from .demo import demo_samples
from .neo_inspect import inspect_neofly, discover_neofly_databases
from .pilot import QUALIFICATIONS, qualification_eligibility, flight_xp
from .contracts import (AirportCatalog, TYPES, TYPE_BY_CODE, PLANE_BY_CODE,
                        generate_offers, eligibility, matches_aircraft)
from .employment import (EMPLOYER_BY_CODE, vacancies, weekly_period,
    employment_eligibility, generate_employer_routes, OWN_MIN_LEVEL, OWN_INVESTMENT)
from .flightplan import export_vfr_plan
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
        self.career = Career(int(self.storage.get_setting("balance") or 5000))
        self.recovered = False
        self.restore_error = None
        try:
            checkpoint = self.storage.get_checkpoint()
            if checkpoint:
                self.career.restore(checkpoint.get("career", {}))
                self.tracker = FlightTracker.from_snapshot(checkpoint["tracker"])
                self.recovered = self.tracker.phase == Phase.AIRBORNE or self.career.mission is not None
        except (KeyError, ValueError, TypeError) as exc:
            self.restore_error = str(exc)
        self.last_checkpoint_time = 0.0
        self.last_sample = None
        self.demo_seq = demo_samples()
        self.demo_index = 0
        self.connected = False
        self.mode = "Desconectado"
        self.balance_var = StringVar(value=f"$ {self.career.balance:,}")
        self.status_var = StringVar(value="Sem conexão • Demo disponível")
        self.pilot_var = StringVar(value="PILOTO • não cadastrado")
        self.pilot_dialog = None
        self.market_dialog = None
        self.employment_dialog = None
        self.airport_catalog = None
        self._refresh_pilot_summary()
        self.info_var = StringVar(value="Sem telemetria")
        self.phase_var = StringVar(value="AGUARDANDO")
        self.mission_var = StringVar(value="Nenhum contrato ativo")
        self.flight_vars = {k: StringVar(value="—") for k in ["ias", "gs", "agl", "alt", "vs", "lat", "lon", "fuel"]}
        self._build()
        if self.restore_error:
            self._log(f"ALERTA: checkpoint não restaurado: {self.restore_error}")
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

        bar = Frame(self.root, bg=PANEL, padx=18, pady=10)
        bar.pack(fill="x", padx=20)
        self.button(bar, "Conectar MSFS", self._connect, accent=True).pack(side="left", padx=(0,8))
        self.button(bar, "Demo sem MSFS", self._demo_start).pack(side="left", padx=(0,8))
        self.button(bar, "Avançar demo", self._demo_next).pack(side="left", padx=(0,8))
        self.button(bar, "Desconectar", self._stop).pack(side="left", padx=(0,8))
        self.button(bar, "Salvar log", self._save_log).pack(side="left", padx=(0,8))
        self.button(bar, "Meu piloto / Habilitações", self._pilot_window, accent=True).pack(side="left")
        Label(bar, textvariable=self.status_var, bg=PANEL, fg=CYAN,
              font=(FONT, 9)).pack(side="right")

        main = Frame(self.root, bg=BG, padx=20, pady=14)
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
            f"{m.origin} → {m.destination}  |  ${m.reward}  | {m.title}" for m in MISSIONS])
        self.mission_select.current(0)
        self.mission_select.pack(fill="x",pady=6)
        self.button(missions,"Aceitar contrato",self._accept,accent=True).pack(fill="x",pady=5)
        Label(missions,textvariable=self.mission_var,bg=PANEL,fg=GOLD,
              font=(FONT,10),wraplength=320,justify="left").pack(anchor="w",pady=8)
        self.button(missions,"Cancelar contrato",self._cancel).pack(fill="x")
        self.button(missions,"Preparar plano VFR da missão",self._prepare_active_plan).pack(fill="x",pady=(7,0))
        self.button(missions,"Vagas e companhias",self._employment_window).pack(fill="x",pady=(7,0))

        logp = self.section(main, "03  /  REGISTRO DE VOO")
        logp.grid(row=1,column=0,sticky="nsew",padx=(0,10))
        self.log_text=Text(logp,bg=PANEL2,fg=FG,insertbackground=CYAN,
                           height=9,font=("Consolas",10),relief="flat",padx=12,pady=12,
                           wrap="word",state="disabled")
        self.log_text.pack(fill="both",expand=True)
        self._log("Bem-vindo. Inicie uma demonstração ou conecte ao MSFS 2020.")
        self._log("O saldo começa em $5.000 em carreira NOVA. Nenhum dado NeoFly foi importado.")

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
                f"      {mission or 'Voo livre'}  +${reward}  avisos estol: {stalls}\n")
        self.history_text.configure(state="disabled")

    def _refresh_pilot_summary(self):
        pilot = self.storage.get_pilot()
        if pilot is None:
            self.pilot_var.set("PILOTO • não cadastrado")
            return
        stats = self.storage.pilot_stats()
        self.pilot_var.set(f"{pilot['callsign']} • NÍVEL {stats['level']} • {stats['xp']} XP")

    def _pilot_window(self):
        if self.pilot_dialog is not None and self.pilot_dialog.winfo_exists():
            self.pilot_dialog.lift()
            self.pilot_dialog.focus_set()
            return
        window = Toplevel(self.root)
        self.pilot_dialog = window
        window.title("FlightSimCarreira • Piloto e habilitações (virtuais)")
        window.geometry("780x720")
        window.minsize(700, 650)
        window.configure(bg=BG)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, "pilot_dialog", None), window.destroy()))

        def redraw():
            for widget in window.winfo_children():
                widget.destroy()
            panel = Frame(window, bg=BG, padx=22, pady=17)
            panel.pack(fill="both", expand=True)
            self.label(panel, "MEU PILOTO  /  BLOCO 01", 17, CYAN, True).pack(anchor="w")
            self.label(panel, "Habilitações e licenças virtuais do jogo; não substituem certificações reais.", 9, MUTED).pack(anchor="w", pady=(3, 12))
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
                        self._log("Piloto cadastrado. Habilitação virtual PPA concedida para os voos iniciais.")
                    else:
                        self.storage.update_pilot(vars_["name"].get(), vars_["callsign"].get(), vars_["home_icao"].get())
                        self._log("Cadastro do piloto atualizado sem alterar histórico ou saldo.")
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
            self.label(panel, "TRILHA DE HABILITAÇÕES", 11, GOLD, True).pack(anchor="w", pady=(5, 6))
            for q in QUALIFICATIONS:
                item = Frame(panel, bg=PANEL2, padx=11, pady=7)
                item.pack(fill="x", pady=3)
                row = Frame(item, bg=PANEL2)
                row.pack(fill="x")
                is_owned = q.code in stats["qualifications"]
                eligible, reason = qualification_eligibility(q.code, stats["qualifications"], stats["flights"], stats["xp"])
                self.label(row, f"{q.code}  •  {q.title}", 10, GREEN if is_owned else FG, True, PANEL2).pack(side="left")
                if eligible and pilot is not None:
                    def grant(code=q.code):
                        try:
                            if self.storage.earn_qualification(code):
                                self._log(f"HABILITAÇÃO VIRTUAL CONCLUÍDA: {code}")
                                redraw()
                        except ValueError as exc:
                            messagebox.showwarning("Habilitação", str(exc), parent=window)
                    self.button(row, "Concluir etapa", grant, accent=True).pack(side="right")
                else:
                    self.label(row, "OBTIDA" if is_owned else reason, 8,
                               GREEN if is_owned else MUTED, bg=PANEL2).pack(side="right")
                self.label(item, q.description, 9, MUTED, bg=PANEL2).pack(anchor="w")
            self.label(panel, "XP novo: 25 por voo registrado + 15 por contrato concluído. "
                       "Os voos anteriores permanecem nas estatísticas; XP anterior não é inventado.",
                       9, MUTED).pack(anchor="w", pady=(9, 3))
            self.label(panel, "Os limites são parâmetros de jogo provisórios. "
                       "As habilitações avançadas ainda não liberam novas aeronaves/contratos nesta versão.",
                       9, MUTED).pack(anchor="w")
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
        if self.mode not in ("MSFS", "Demo") or self.last_sample is None:
            messagebox.showwarning("Contrato", "Conecte ao MSFS e aguarde telemetria em solo.")
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
            self.career.accept(m,self.last_sample)
            self._show_mission()
            self._checkpoint(force=True)
            self._log(f"Contrato aceito: {m.title} ({m.origin} → {m.destination}).")
            if m.freelance:
                plane = PLANE_BY_CODE[m.employer_plane]
                self._log(f"FREELANCER: avião fornecido pelo contratante: {plane.name}.")
                self._log("Selecione este modelo no MSFS antes de decolar; o addon NÃO muda o avião automaticamente.")
                if not matches_aircraft(self.last_sample.aircraft_title, m.employer_plane):
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
        columns = ("kind", "origin", "destination", "pay", "plane")
        table = ttk.Treeview(wrapper,columns=columns,show="headings",height=13,selectmode="browse")
        for key,title,width in [("kind","TIPO",240),("origin","SAÍDA",85),
                                 ("destination","DESTINO",100),("pay","PAGAMENTO",110),
                                 ("plane","AVIÃO CONTRATANTE",260)]:
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
                    f"${m.reward:,}",PLANE_BY_CODE[m.employer_plane].name if m.freelance else "—"))
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
            path=export_vfr_plan(m,state_dir()/'planos_vfr')
        except (OSError,ValueError) as exc:
            messagebox.showerror('Plano VFR',str(exc))
            return
        self._log(f'Plano VFR exportado: {path}')
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
                    ','.join(v.qualifications),v.plane,f'${v.salary:,}/sem',
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
        self.label(panel,f'A partir do nível {OWN_MIN_LEVEL}, 25 h, PLA e ${OWN_INVESTMENT:,} de capital.',9,MUTED).pack(anchor='w')
        comp_name=StringVar(value='')
        entry=Entry(panel,textvariable=comp_name,font=(FONT,10),bg=PANEL2,fg=FG,insertbackground=FG,relief='flat')
        entry.pack(side='left',fill='x',expand=True,padx=(0,10),pady=5,ipady=7)
        def create_company():
            if not guard():return
            if not messagebox.askyesno('Criar companhia',f'Investir ${OWN_INVESTMENT:,} para registrar a companhia virtual?',parent=window):return
            try:
                result=self.storage.found_company(comp_name.get(),time())
                self.career.balance=int(self.storage.get_setting('balance'))
                self.balance_var.set(f'$ {self.career.balance:,}')
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
        self._show_mission()
        self._checkpoint(force=True)
        self._log("Contrato cancelado. Não houve pagamento.")

    def _show_mission(self):
        m = self.career.mission
        self.mission_var.set((f"ATIVA  {m.origin} → {m.destination}  |  ${m.reward}"
            + (f"  •  FREELANCER: {PLANE_BY_CODE[m.employer_plane].name}" if m.freelance else ""))
            if m else "Nenhum contrato ativo")

    def _checkpoint_data(self, tracker=None):
        return {"version": 1, "career": self.career.snapshot(),
                "tracker": (tracker or self.tracker).snapshot()}

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

    def _process_sample(self,s):
        self.last_sample=s
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
        old_balance = self.career.balance
        events = self.tracker.update(s)
        completion_payment = self.career.evaluate(events, s.aircraft_title)
        self.phase_var.set(self.tracker.phase.value.upper())
        for e in events:
            if e["type"] == "takeoff":
                self._log("DECOLAGEM detectada. Diário iniciado e salvo para recuperação.")
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
                try:
                    inserted = self.storage.finalize_flight(start, e, v, self.tracker.stalls,
                                        payment["mission"] if payment else None,
                                        payment["reward"] if payment else 0, checkpoint_after,
                                        aircraft_title=s.aircraft_title)
                except Exception as exc:
                    self._log(f"FALHA AO SALVAR pouso: {exc}. Não feche antes de exportar log.")
                    self.status_var.set("Erro ao salvar voo")
                    self.career.restore(old_career_state)
                    self.career.balance = old_balance
                    # O checkpoint anterior mantém a fase em voo; ao reiniciar,
                    # o app poderá confirmar novamente o pouso em solo.
                    return
                self.tracker = next_tracker
                self.career.balance = int(self.storage.get_setting("balance") or 5000)
                actual_credit = int(self.storage.get_setting("balance") or 5000) - old_balance
                if inserted and self.storage.get_pilot() is not None:
                    self._log(f"PROGRESSO DO PILOTO: +{flight_xp(actual_credit)} XP pelo voo concluído.")
                    self._refresh_pilot_summary()
                if not inserted:
                    self._log("Pouso já salvo anteriormente: pagamento duplicado bloqueado.")
                    saved = self.storage.get_checkpoint()
                    if saved:
                        self.career.restore(saved.get("career", {}))
                elif payment and actual_credit > 0:
                    self._log(f"CONTRATO CONCLUÍDO: +${actual_credit} em nossa carreira.")
                elif payment:
                    self._log("Contrato já pago anteriormente. Novo crédito bloqueado.")
                else:
                    self._log("Voo registrado; contrato não concluído (confira origem e destino).")
                self.balance_var.set(f"$ {self.career.balance:,}")
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
                elif kind=='plan_error':
                    self._log('PLANO VFR: '+item)
                    messagebox.showwarning('Plano VFR',item)
                elif kind=="disconnected":
                    self.connected=False
                    self.status_var.set(item)
        except Empty:
            pass
        self.root.after(200,self._poll)

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
        if self.sim:
            self.sim.stop()
        self.storage.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
