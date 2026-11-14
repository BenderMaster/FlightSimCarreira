"""Allowlisted UI commands; all actions execute on Application's Tk thread."""
import os
import sqlite3
from zipfile import BadZipFile
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
from . import pilot_career, financial_center, airline_operations as airline, flight_history, type_ratings, settings_center

class DashboardController:
    def __init__(self,app):
        self.app=app;self.closed=False;self.process=None;self.fallback=False
        self.presenter=DashboardPresenter(app)
        self.server=DashboardServer()
        self.presenter.photo_url_for=self.server.photo_url
        self.server.set_photos(photo_bytes(app.storage))
        self.last_payroll_check=0
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
            if time()-getattr(self,'last_payroll_check',time())>=30:
                self.last_payroll_check=time()
                settled=app.storage.airline_payroll(time()) if (app:=self.app) else []
                if settled:
                    app.career.balance=int(app.storage.get_setting('balance') or 0)
                    app.balance_var.set(brl(app.career.balance))
                    self.presenter.pilot_career_cache=None
                    self.presenter.finance_cache=None
                    self._airline_notice(True,'Folha semanal encerrada: '+
                        '; '.join(airline.EMPLOYER_BY_CODE[e['company']].name+
                        ' • '+brl(e['salary'])+' / '+str(e['xp'])+' XP' for e in settled))
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
        app=self.app;w=Toplevel(app.root);w.title('FlightSim • Configurações');w.geometry('640x660');w.configure(bg='#081421')
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
                target=self.app.profile_dir/'pilot-avatar.png';im.save(target,'PNG')
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
            title='Fotografia da aeronave no FlightSim',
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

    def _airline_notice(self,ok,message,action='airline'):
        app=self.app
        app.airline_notice_seq=getattr(app,'airline_notice_seq',0)+1
        app.airline_notice=dict(seq=app.airline_notice_seq,ok=ok,
                                message=message,action=action)
        app._log('COMPANHIAS: '+message)

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
        elif action=='pilot_event_ack':
            try:
                event_id=cmd.get('id','')
                if not isinstance(event_id,str) or not event_id.isascii() or not event_id.isdecimal():
                    raise ValueError('Evento inválido')
                pilot_career.acknowledge_event(app.storage,int(event_id))
                self.presenter.pilot_career_cache=None
            except (ValueError,TypeError):
                app._log('CONQUISTAS: confirmação inválida; notificação preservada.')
        elif action in ('settings_set','settings_scan','settings_backup',
                        'settings_restore','settings_export_log','settings_open_data'):
            try:
                if action=='settings_set':
                    request=cmd['payload'];key=request['key'];value=request['value']
                    if key in ('fuel','tax','failures'):
                        if type(value) is not bool:
                            raise ValueError('Opção inválida.')
                        if app.tracker.phase==Phase.AIRBORNE:
                            raise ValueError('Altere regras da carreira somente em solo.')
                        if key=='fuel':
                            app.storage.set_setting('fuel_control_enabled','1' if value else '0')
                            message='Combustível '+('ativado.' if value else 'desativado: -30% R$/XP nos voos seguintes.')
                        elif key=='tax':
                            app.storage.set_setting('income_tax_enabled','1' if value else '0')
                            message='Imposto virtual '+('ativado.' if value else 'desativado.')
                            self.presenter.finance_cache=None
                        else:
                            app.storage.set_setting('simulated_failures_enabled','1' if value else '0')
                            message='Preferência de falhas registrada; injeção de falhas ainda NÃO está implementada.'
                    else:
                        app.settings_prefs=settings_center.save_global(app.profiles.root,key,value)
                        if key=='reconnect' and app.sim:
                            app.sim.reconnect=value
                        message='Preferência '+key+' salva.'
                elif action=='settings_scan':
                    from .aircraft_catalog import detect_package_roots, scan_installed_aircraft
                    roots=detect_package_roots()
                    if not roots:
                        folder=filedialog.askdirectory(parent=app.root,
                            title='Selecione a pasta InstalledPackages do MSFS')
                        if not folder:
                            raise ValueError('Busca cancelada.')
                        roots=[__import__('pathlib').Path(folder)]
                    installed=scan_installed_aircraft(roots)
                    codes={aircraft_model(x.title) for x in installed}
                    app.airline_available_codes.update(x for x in codes if x)
                    app.airline_scan_count=len(installed)
                    self.presenter.market_key=None
                    self.presenter.refresh_market(force=True)
                    message=str(len(installed))+' variações encontradas; modelos reconhecidos: '+str(len(codes-{None}))+'. Leitura não comprova licença de uso.'
                elif action=='settings_backup':
                    filename=filedialog.asksaveasfilename(parent=app.root,
                        title='Backup de todas as carreiras',defaultextension='.zip',
                        filetypes=[('FlightSim backup','*.zip')],
                        initialfile='FlightSim-carreiras-backup.zip')
                    if not filename:raise ValueError('Backup cancelado.')
                    count=settings_center.export_profiles(app,filename)
                    message='Backup salvo com segurança: '+str(count)+' perfil(is).'
                elif action=='settings_restore':
                    if app.tracker.phase==Phase.AIRBORNE or app.career.mission:
                        raise ValueError('Finalize o voo e o contrato antes de importar perfis.')
                    filename=filedialog.askopenfilename(parent=app.root,title='Importar backup FlightSim',
                        filetypes=[('FlightSim backup','*.zip')])
                    if not filename:raise ValueError('Restauração cancelada.')
                    if not messagebox.askyesno('Importar carreiras',
                        'Os pilotos do arquivo serão importados como NOVOS perfis. Nenhuma carreira existente será substituída. Continuar?',
                        parent=app.root):
                        raise ValueError('Importação cancelada.')
                    names=settings_center.import_profiles(app,filename)
                    message=str(len(names))+' carreira(s) importada(s). Troque pelo Gerenciador de Pilotos.'
                    self.presenter.pilot_career_cache=None
                elif action=='settings_export_log':
                    filename=filedialog.asksaveasfilename(parent=app.root,title='Salvar diagnóstico',
                        defaultextension='.txt',filetypes=[('Texto','*.txt')],
                        initialfile='FlightSim-diagnostico.txt')
                    if not filename:raise ValueError('Exportação cancelada.')
                    raw=app.log_text.get('1.0','end')
                    clean=settings_center.sanitize_log(raw,app.settings_prefs['redact_diagnostics'])
                    with open(filename,'w',encoding='utf-8') as handle:
                        handle.write('FlightSim • Diagnóstico local\n'+clean)
                    message='Diagnóstico exportado; revise antes de compartilhar.'
                else:
                    if sys.platform!='win32':
                        raise ValueError('Abertura da pasta disponível no Windows.')
                    from .app import state_dir
                    os.startfile(str(state_dir()))
                    message='Pasta de dados aberta.'
                ok=True
            except (OSError,ValueError,TypeError,KeyError,RuntimeError,ImportError,
                    BadZipFile,sqlite3.DatabaseError) as exc:
                ok=False
                message='Operação não concluída: '+str(exc)
            app.settings_notice_seq=getattr(app,'settings_notice_seq',0)+1
            app.settings_notice=dict(seq=app.settings_notice_seq,ok=ok,message=message)
            app._log('CONFIGURAÇÕES: '+message)
        elif action=='flight_note':
            try:
                payload=cmd['payload']
                flight_history.save_note(app.storage,payload['flight_id'],payload['note'])
                self.presenter.history_cache=None
                app._log('LOGBOOK: anotação salva para o voo #'+str(payload['flight_id']))
            except (ValueError,TypeError,KeyError) as exc:
                app._log('LOGBOOK: '+str(exc))
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
        elif action=='flightops_preview':
            # Prévia volátil: o editor nunca grava SQLite antes de Salvar.
            try:
                route=app._flightops_preview(cmd.get('payload'))
                app.flightops_preview={'id':cmd['id'],'route':route,'error':None}
            except (ValueError,TypeError,KeyError) as exc:
                app.flightops_preview={'id':cmd['id'],'route':None,'error':str(exc)}
        elif action in ('flightops_save','flightops_export','flightops_send','flightops_clear'):
            try:
                if action=='flightops_save':
                    message=app._flightops_save(cmd.get('payload'))
                elif action=='flightops_clear':
                    message=app._flightops_clear()
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
        elif action in ('pilot_profile_create','pilot_profile_update','pilot_profile_switch',
                        'pilot_profile_reset','pilot_showcase','pilot_medal_equip','pilot_license_claim'):
            try:
                if action=='pilot_profile_create':message=app._profile_create(cmd.get('payload'))
                elif action=='pilot_profile_update':message=app._profile_update(cmd.get('payload'))
                elif action=='pilot_profile_switch':message=app._relaunch_profile(target=cmd.get('id'))
                elif action=='pilot_profile_reset':message=app._relaunch_profile(reset=True)
                elif action=='pilot_showcase':message=app._pilot_showcase(cmd.get('payload'))
                elif action=='pilot_license_claim':
                    code=cmd.get('id')
                    if not isinstance(code,str):raise ValueError('Código de licença inválido.')
                    granted=app.storage.earn_qualification(code)
                    message='Licença '+code+' conquistada.' if granted else 'Licença já registrada.'
                else:message=app._pilot_equip(cmd.get('id'))
                ok=True
            except (ValueError,TypeError,KeyError,OSError) as exc:
                ok=False;message='Operação recusada: '+str(exc)
            if not self.closed:
                app.pilot_career_notice_seq=getattr(app,'pilot_career_notice_seq',0)+1
                app.pilot_career_notice=dict(seq=app.pilot_career_notice_seq,ok=ok,
                                             message=message,action=action)
                self.presenter.pilot_career_cache=None
                app._log('PILOTO: '+message)
        elif action in ('finance_loan','finance_repay','finance_tax','finance_export'):
            try:
                if action=='finance_export':
                    # CSV completo montado na thread Tk (SQLite não é thread-safe).
                    if cmd.get('id') is not None:
                        raise ValueError('Exportação não aceita parâmetros.')
                    csv_bytes=financial_center.export_csv(app.storage)
                    self.server.set_finance_csv(csv_bytes)
                    message='Extrato integral preparado para download.'
                else:
                    if app.tracker.phase==Phase.AIRBORNE:
                        raise ValueError('Operações financeiras disponíveis somente em solo.')
                    value=cmd.get('id')
                    if action=='finance_tax':
                        if value not in ('0','1'):
                            raise ValueError('Opção de imposto inválida.')
                        app.storage.set_setting('income_tax_enabled',value)
                        message='Imposto virtual de 4% '+('ativado' if value=='1' else 'desativado')+'.'
                    else:
                        import re
                        if not isinstance(value,str) or not re.fullmatch(
                            r'(?:0|[1-9][0-9]{0,5})\|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value):
                            raise ValueError('Formato financeiro inválido.')
                        amount_str,request_id=value.split('|',1)
                        amount=int(amount_str)
                        if action=='finance_loan':
                            app.storage.take_loan(amount,request_id=request_id)
                            message='Empréstimo de '+brl(amount)+' contratado. Dívida: '+brl(app.storage.outstanding_loan())+'.'
                        else:
                            app.storage.repay_loan(amount,request_id=request_id)
                            message='Parcela de '+brl(amount)+' quitada. Dívida restante: '+brl(app.storage.outstanding_loan())+'.'
                    app.career.balance=int(app.storage.get_setting('balance') or 0)
                    app.balance_var.set(brl(app.career.balance))
                ok=True
            except (ValueError,TypeError,KeyError,OSError) as exc:
                ok=False
                message='Operação recusada: '+str(exc)
            app.finance_notice_seq=getattr(app,'finance_notice_seq',0)+1
            app.finance_notice=dict(seq=app.finance_notice_seq,ok=ok,
                                    message=message,action=action)
            self.presenter.finance_cache=None
            app._log('FINANÇAS: '+message)
        elif action in ('airline_apply','airline_review','airline_resign',
                          'airline_found','airline_buy_plane'):
            try:
                if app.tracker.phase==Phase.AIRBORNE or app.career.mission:
                    raise ValueError('Finalize/cancele o contrato e permaneça em solo.')
                value=cmd.get('id')
                if action=='airline_apply':
                    if not isinstance(value,str) or '|' not in value:
                        raise ValueError('Selecione vaga e compromisso semanal.')
                    vacancy_id,tier_s=value.rsplit('|',1)
                    if tier_s not in ('0','10','20'):
                        raise ValueError('Compromisso inválido.')
                    region=(self.presenter.center.icao if self.presenter.center
                            else app.storage.get_pilot()['home_icao'])
                    vacancy=next((v for v in airline.vacancies(
                        airline.weekly_period(time()),region)
                        if v.id==vacancy_id),None)
                    if vacancy is None:raise ValueError('Vaga expirada.')
                    app.storage.apply_vacancy(vacancy,time(),int(tier_s))
                    message='Candidatura enviada com compromisso '+tier_s+'%. A seleção é semanal.'
                elif action=='airline_review':
                    results=app.storage.review_applications(time())
                    paid=app.storage.airline_payroll(time())
                    self.presenter.refresh_market(force=True)
                    message=('Seleção: '+', '.join(x['company']+' '+x['result'] for x in results)
                        if results else 'Seleção ainda em análise.')
                    if paid:message+=' Folha encerrada: '+', '.join(brl(x['salary'])+' / '+str(x['xp'])+' XP' for x in paid)
                elif action=='airline_resign':
                    app.storage.resign_employment(time())
                    self.presenter.refresh_market(force=True)
                    message='Vínculo encerrado. Progresso já registrado foi preservado.'
                elif action=='airline_found':
                    if not isinstance(value,str):raise ValueError('Nome de companhia obrigatório.')
                    result=app.storage.found_company(value,time())
                    self.presenter.refresh_market(force=True)
                    message='Companhia '+result['owner_company']+' fundada com aporte de R$ 400.000.'
                else:
                    if value not in airline.AIRCRAFT_ECONOMY:raise ValueError('Modelo inválido.')
                    plane=airline.AIRCRAFT_ECONOMY[value]
                    app.storage.company_buy_plane(value)
                    self.presenter.refresh_market(force=True)
                    message='Aeronave empresarial adquirida: '+plane.title+' • '+brl(plane.purchase_price)
                app.career.balance=int(app.storage.get_setting('balance') or 0)
                app.balance_var.set(brl(app.career.balance))
                self.presenter.finance_cache=None
                self.presenter.pilot_career_cache=None
                self._airline_notice(True,message,action)
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                self._airline_notice(False,'Operação recusada: '+str(exc),action)
        elif action=='prepare':
            if not app.career.mission:
                app._log('DESPACHO: aceite um contrato antes de preparar plano e carga.');return
            app._prepare_active_plan(automatic=True)
            app._queue_payload_load()
            app._checkpoint(force=True)
        elif action=='refresh':
            app.airport_details.clear()
            app.airport_details_requested.clear()
            app.airport_detail_started.clear()
            app.airport_details_next=0.0
            self.presenter.refresh_market(True)
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
