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
from .fleet_photos import normalize_photo, save_photo, delete_photo, photo_bytes, owned_fleet
from .aircraft_marketplace import execute_market

class DashboardController:
    def __init__(self,app):
        self.app=app;self.closed=False;self.process=None;self.fallback=False
        self.presenter=DashboardPresenter(app)
        self.server=DashboardServer()
        self.presenter.photo_url_for=self.server.photo_url
        self.server.set_photos(photo_bytes(app.storage))
        self.server.publish(self.presenter.snapshot());self.server.start()
        self.tick_id=app.root.after(500,self.tick)
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
        self.tick_id=self.app.root.after(500,self.tick)

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

    def _owned_ref(self,ref):
        if not isinstance(ref,str) or len(ref)>80:
            raise ValueError('Identificador de aeronave inválido.')
        plane=next((p for p in owned_fleet(self.app.storage) if p['ref']==ref),None)
        if plane is None:raise ValueError('Aeronave não pertence à frota adquirida.')
        return plane

    def _fleet_photo_upload(self,ref):
        self._owned_ref(ref)
        path=filedialog.askopenfilename(
            parent=self.app.root,
            title='Fotografia da aeronave no FlightSimCarreira',
            filetypes=[('Imagens','*.png *.jpg *.jpeg *.webp *.bmp'),('Todos os arquivos','*.*')])
        if not path:return
        try:
            jpeg=normalize_photo(path)
            save_photo(self.app.storage,ref,jpeg)
            self.server.set_photo(ref,jpeg)
            self.app._log('FROTA: fotografia personalizada salva no SQLite para '+ref)
        except (OSError,ValueError) as exc:
            messagebox.showerror('Fotografia da frota',str(exc),parent=self.app.root)

    def _fleet_service(self,ref):
        app=self.app
        plane=self._owned_ref(ref)
        if app.tracker.phase==Phase.AIRBORNE:
            app._log('MANUTENÇÃO: proibida durante voo.')
            return
        if not messagebox.askyesno('Revisar aeronave',
                'Executar manutenção de '+plane['title']+'? O custo será descontado da carreira.',
                parent=app.root):
            return
        try:
            if ref.startswith('legacy:'):
                app.storage.service_aircraft(plane['code'])
            else:
                app.storage.fleet_manager().service(ref)
            app.career.balance=int(app.storage.get_setting('balance') or 0)
            app.balance_var.set(brl(app.career.balance))
            app._log('FROTA: manutenção executada em '+plane['title'])
        except (ValueError,KeyError) as exc:
            app._log('MANUTENÇÃO: '+str(exc))

    def dispatch(self,cmd):
        app=self.app;action=cmd['action']
        mapping={'pilot':app._pilot_window,'market':app._market_window,'fleet':app._fleet_window,
            'planning':app._planning_window,'finance':app._finance_window,'employment':app._employment_window,
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
        elif action in ('fleet_select','fleet_photo','fleet_photo_clear','fleet_service'):
            try:
                ref=cmd.get('id')
                plane=self._owned_ref(ref)
                if action=='fleet_select':
                    if app.tracker.phase==Phase.AIRBORNE:
                        raise ValueError('Não altere a aeronave ativa durante um voo.')
                    app.storage.fleet_manager().select(ref)
                    app._log('FROTA: aeronave selecionada: '+plane['title']+' ('+ref+')')
                elif action=='fleet_photo':
                    self._fleet_photo_upload(ref)
                elif action=='fleet_photo_clear':
                    if delete_photo(app.storage,ref):
                        self.server.remove_photo(ref)
                        app._log('FROTA: fotografia personalizada removida para '+ref)
                elif action=='fleet_service':
                    self._fleet_service(ref)
            except ValueError as exc:
                app._log('FROTA: '+str(exc))
        elif action in ('aircraft_buy_new','aircraft_buy_used','aircraft_rent','aircraft_sell'):
            try:
                if action=='aircraft_sell':
                    previous_ref=str(cmd.get('id','')).split('|')[0]
                else:
                    previous_ref=None
                message=execute_market(app,self.presenter.center,action,cmd.get('id'))
                if previous_ref:self.server.remove_photo(previous_ref)
                app._log('MERCADO AERONAVES: '+message)
                ok=True
            except (ValueError,KeyError,TypeError) as exc:
                message='Operação recusada: '+str(exc)
                app._log('MERCADO AERONAVES: '+message)
                ok=False
            seq=getattr(app,'aircraft_market_notice_seq',0)+1
            app.aircraft_market_notice_seq=seq
            app.aircraft_market_notice=dict(seq=seq,ok=ok,message=message,action=action)
        elif action in ('flightops_save','flightops_export','flightops_send'):
            try:
                if action=='flightops_save':
                    message=app._flightops_save(cmd.get('payload'))
                else:
                    message=app._flightops_export(send=action=='flightops_send')
                ok=True
            except (ValueError,TypeError,KeyError,OSError) as exc:
                message='Planejamento recusado: '+str(exc)
                app._log('FLIGHT OPS: '+message)
                ok=False
            seq=getattr(app,'flightops_notice_seq',0)+1
            app.flightops_notice_seq=seq
            app.flightops_notice=dict(seq=seq,ok=ok,message=message,action=action)
        elif action=='prepare':
            if not app.career.mission:
                app._log('DESPACHO: aceite um contrato antes de preparar plano e carga.');return
            app._prepare_active_plan(automatic=True)
            app._queue_payload_load()
            app._checkpoint(force=True)
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
        elif action=='refuel':
            # O popup HTML já é a confirmação da quantidade; não abrir Tk extra.
            fm=app.storage.fleet_manager();plane=fm.selected();sample=app.last_sample
            if not plane or app.tracker.phase==Phase.AIRBORNE:
                app._log('ABASTECIMENTO: selecione aeronave própria em solo.');return
            if app.career.mission and app.career.mission.freelance:
                app._log('ABASTECIMENTO: avião do contratante não aceita combustível pessoal.');return
            if not (app.mode=='MSFS' and app.connected and app.sim and sample and sample.on_ground
                    and time()-sample.timestamp<10
                    and aircraft_model(sample.aircraft_title)==plane['code']):
                app._log('ABASTECIMENTO: MSFS e modelo selecionado devem estar conectados em solo.');return
            try:
                litres=float(cmd.get('id'))
                # Mudança de combustível pode ultrapassar o MTOW, mesmo se
                # o peso da carga estava válido antes. Nunca comprar acima.
                previous=app.fuel_manager.get(plane['ref'])
                if previous and sample.total_weight_lbs is not None and sample.max_gross_weight_lbs is not None:
                    from .finance import LITERS_PER_GALLON
                    current_litres=sum(previous['tanks'].values())*LITERS_PER_GALLON
                    projected=sample.total_weight_lbs+(litres-current_litres)*1.58733
                    if projected>sample.max_gross_weight_lbs-1:
                        raise ValueError('Combustível deixaria o avião acima do MTOW. Reduza a quantidade.')
                result=app.fuel_manager.change_liters(plane['ref'],litres)
                app.pending_fuel_ref=plane['ref']
                app.sim.request_fuel_restore(result['tanks'])
                app.career.balance=int(app.storage.get_setting('balance') or 0)
                app.balance_var.set(brl(app.career.balance))
                app._log('ABASTECIMENTO: meta %.1f L; compra %s; reembolso %s. Enviado ao MSFS para leitura posterior.'%(
                    result['target_liters'],brl(result['cost_brl']),brl(result['refund_brl'])))
            except (ValueError,TypeError,KeyError) as exc:
                app._log('ABASTECIMENTO RECUSADO: '+str(exc))
        elif action=='service':
            fm=app.storage.fleet_manager();plane=fm.selected()
            if not plane or app.tracker.phase==Phase.AIRBORNE:
                messagebox.showwarning('Frota','Aeronave própria em solo necessária.');return
            if not messagebox.askyesno('Frota','Revisar a aeronave e cobrar na carreira?'):
                return
            try:
                result=fm.service(plane['ref'])
                app.career.balance=int(app.storage.get_setting('balance') or 0)
                app.balance_var.set(brl(app.career.balance))
                app._log('MANUTENÇÃO: '+str(result))
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
