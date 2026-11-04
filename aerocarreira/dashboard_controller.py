"""Allowlisted UI commands; all actions execute on Application's Tk thread."""
import os
import subprocess
import sys
from queue import Empty
from time import time
from tkinter import Toplevel, Text, END, filedialog, messagebox
from .domain import Phase
from .contracts import aircraft_model
from .finance import brl
from .dashboard import DashboardPresenter
from .midnight_server import DashboardServer

class DashboardController:
    def __init__(self,app):
        self.app=app;self.closed=False;self.process=None;self.fallback=False
        self.presenter=DashboardPresenter(app)
        self.server=DashboardServer();self.server.publish(self.presenter.snapshot());self.server.start()
        self.tick_id=app.root.after(250,self.tick)
        if os.getenv('FLIGHTSIM_HEADLESS')!='1':
            args=([sys.executable,'--webview-host',self.server.url] if getattr(sys,'frozen',False) else [sys.executable,'-m','aerocarreira.webview_host',self.server.url])
            self.process=subprocess.Popen(args)
        app.root.withdraw()

    def tick(self):
        if self.closed:return
        try:
            for _ in range(8):
                try:command=self.server.commands.get_nowait()
                except Empty:break
                self.dispatch(command)
                if self.closed:return
            self.server.publish(self.presenter.snapshot())
            if self.process and self.process.poll() is not None:
                if self.process.returncode:
                    messagebox.showerror('Midnight Ops','A janela WebView não iniciou. Execute instalar_windows.bat e confirme o Microsoft Edge WebView2 Runtime. A interface clássica será aberta.')
                    self.process=None
                    self.fallback=True
                    self.app.root.deiconify()
                else:self.app._close();return
        except Exception as exc:
            self.app._log('Dashboard: '+str(exc))
        self.tick_id=self.app.root.after(250,self.tick)

    def show_text(self,title,text):
        w=Toplevel(self.app.root);w.title(title);w.geometry('900x580');w.configure(bg='#081421')
        t=Text(w,bg='#0d1b2a',fg='#eaf6ff',font=('Consolas',11),wrap='word',padx=20,pady=20)
        t.pack(fill='both',expand=True);t.insert(END,text);t.configure(state='disabled');w.lift();w.focus_force()

    def settings(self):
        app=self.app;w=Toplevel(app.root);w.title('FlightSimCarreira • Configurações');w.geometry('640x660');w.configure(bg='#081421')
        app.label(w,'CONEXÃO E FERRAMENTAS',16,bold=True).pack(padx=20,pady=20)
        for label,command in [('Conectar MSFS',app._connect),('Desconectar',app._stop),('Demo sem MSFS',app._demo_start),
            ('Avançar demo',app._demo_next),('Contratos legados de teste',self.legacy),('Cancelar contrato',app._cancel),
            ('Salvar log',app._save_log),('Aeronaves instaladas',app._installed_aircraft_window),
            ('Analisar NeoFly',app._analyze),('Localizar NeoFly',app._locate_neofly),('Painel local experimental',app._open_local_panel)]:
            app.button(w,label,command).pack(fill='x',padx=20,pady=3)
        w.lift();w.focus_force()

    def legacy(self):
        from .domain import MISSIONS
        w=Toplevel(self.app.root);w.title('Contratos legados de teste');w.configure(bg='#081421')
        for i,m in enumerate(MISSIONS):
            def choose(index=i):
                self.app.mission_select.current(index);self.app._accept()
            self.app.button(w,m.title+' • '+m.origin+' → '+m.destination,choose).pack(fill='x',padx=15,pady=8)

    def avatar(self):
        from PIL import Image,ImageOps
        from .app import state_dir
        path=filedialog.askopenfilename(title='Foto do piloto',filetypes=[('Imagens','*.png *.jpg *.jpeg *.webp')])
        if not path:return
        try:
            with Image.open(path) as im:
                im=ImageOps.exif_transpose(im).convert('RGB')
                im=ImageOps.fit(im,(256,256),method=Image.Resampling.LANCZOS)
                target=state_dir()/'pilot-avatar.png';im.save(target,'PNG')
            self.app.storage.set_setting('pilot_avatar_v1',str(target))
            self.presenter.avatar_key=None
        except (OSError,ValueError,Image.DecompressionBombError) as exc:messagebox.showerror('Foto',str(exc))

    def dispatch(self,cmd):
        app=self.app;action=cmd['action']
        mapping={'pilot':app._pilot_window,'market':app._market_window,'fleet':app._fleet_window,
            'planning':app._prepare_mission_button,'finance':app._finance_window,'employment':app._employment_window,
            'connect':app._connect,'disconnect':app._stop,'demo':app._demo_start,'demo_next':app._demo_next,
            'cancel':app._cancel,'plan':app._prepare_active_plan,'close':app._close,'avatar':self.avatar,
            'settings':self.settings,'legacy':self.legacy,'save_log':app._save_log,'installed':app._installed_aircraft_window,
            'analyze':app._analyze,'locate':app._locate_neofly,'local_panel':app._open_local_panel}
        if action in mapping:
            mapping[action]()
            # Native dialogs are real existing flows, brought in front of the WebView.
            if not self.closed:
                for child in app.root.winfo_children():
                    if isinstance(child,Toplevel):child.lift();child.focus_force()
        elif action=='refresh':self.presenter.refresh_market(True)
        elif action=='history':self.show_text('Diário de bordo',app.history_text.get('1.0','end'))
        elif action=='reports':self.show_text('Análise e relatórios','Módulo de análise avançada em desenvolvimento.\n\nREGISTRO DA SESSÃO\n\n'+app.log_text.get('1.0','end'))
        elif action=='offer':
            self.presenter.refresh_market(True)
            m=self.presenter.offers.get(cmd.get('id'))
            if not m or app.storage.contract_completed(m.id):
                messagebox.showwarning('Mercado','Oferta expirada ou concluída. Atualize a lista.');return
            # O botão "Aceitar missão" já confirma explicitamente dentro da
            # janela WebView2; não abrir messagebox Tk atrás do app.
            # O motor da carreira revalida fase/solo, localização,
            # elegibilidade e contrato ativo em _accept_specific().
            app._accept_specific(m)
        elif action=='fuel':
            if app.tracker.phase==Phase.AIRBORNE:
                messagebox.showwarning('Combustível','Altere apenas em solo. O modo fica congelado na decolagem.');return
            enabled=app.storage.get_setting('fuel_control_enabled')=='1'
            if not enabled or messagebox.askyesno('Controle de combustível','Desligar aplica -30% de dinheiro e XP aos próximos voos. Confirmar?'):
                app.storage.set_setting('fuel_control_enabled','0' if enabled else '1')
                app._log('Controle de combustível '+('desligado.' if enabled else 'ativado.'))
        elif action=='refuel_set':
            fm=app.storage.fleet_manager();plane=fm.selected();s=app.last_sample
            try:
                if not plane or (app.career.mission and app.career.mission.freelance):
                    raise ValueError('Selecione uma aeronave da sua frota.')
                if (app.mode!='MSFS' or not app.connected or not s or not s.on_ground
                        or time()-s.timestamp>=10 or aircraft_model(s.aircraft_title)!=plane['code']):
                    raise ValueError('Conecte a aeronave selecionada no solo antes de abastecer.')
                if app.tracker.phase==Phase.AIRBORNE:
                    raise ValueError('Não é permitido abastecer em voo.')
                requested=cmd.get('id','')
                # A validação completa e controle de crédito ocorrem no FuelManager.
                result=app.fuel_manager.set_target_liters(plane['ref'],requested)
                if app.sim:app.sim.request_fuel_restore(result['tanks'])
                app.career.balance=int(app.storage.get_setting('balance') or 0)
                app.balance_var.set(brl(app.career.balance))
                app.refuel_feedback={'status':'success','ts':time(),'message':
                    ('Devolução: '+brl(result['refund_brl']) if result['refund_brl'] else
                     'Abastecimento: '+brl(result['cost_brl']))+
                    f" • tanque {result['target_liters']:.1f} L. Aguardando leitura SimConnect."}
                app._log('ABASTECIMENTO: '+app.refuel_feedback['message'])
            except (ValueError,TypeError,OSError) as exc:
                app.refuel_feedback={'status':'error','ts':time(),'message':str(exc)}
                app._log('ABASTECIMENTO BLOQUEADO: '+str(exc))
        elif action in ('refuel','service'):
            fm=app.storage.fleet_manager();plane=fm.selected();s=app.last_sample
            if app.tracker.phase==Phase.AIRBORNE:messagebox.showwarning('Frota','Operação permitida somente em solo.');return
            if not plane:messagebox.showwarning('Frota','Selecione sua aeronave no Hangar.');return
            if app.career.mission and app.career.mission.freelance:
                messagebox.showwarning('Frota','O contrato utiliza aeronave do contratante. Gerencie sua frota pelo Hangar.');return
            if action=='refuel':
                # Compatibilidade com a interface Tk clássica; Midnight usa popup próprio.
                messagebox.showinfo('Abastecimento','Use o popup Abastecer no painel Midnight para informar litros.')
                return
            if not messagebox.askyesno('Frota','Revisar aeronave com cobrança na carreira?'):return
            try:
                result=app.fuel_manager.refuel_full(plane['ref']) if action=='refuel' else fm.service(plane['ref'])
                app.career.balance=int(app.storage.get_setting('balance') or 0);app.balance_var.set(brl(app.career.balance))
                app._log(('ABASTECIMENTO' if action=='refuel' else 'MANUTENÇÃO')+': '+str(result))
            except (ValueError,KeyError) as exc:messagebox.showwarning('Frota',str(exc))

    def stop(self):
        if self.closed:return
        self.closed=True
        self.app.root.after_cancel(self.tick_id)
        self.server.stop()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
