"""Dashboard Midnight Ops (fase 1): apresentação dos dados reais, sem mudar o motor.

Tkinter puro: instalado junto com Python para Windows. Todas as ações sensíveis
chamam os métodos existentes de Application; mapa esquemático, não carta VFR.
"""
from __future__ import annotations
from math import isfinite
from pathlib import Path
from time import time
from tkinter import (Frame, Label, Button, Canvas, Text, PhotoImage, Toplevel,
                     Scrollbar, StringVar, Checkbutton, IntVar, messagebox, END)
from tkinter import ttk
from .contracts import (AirportCatalog, generate_offers, eligibility,
                        TYPE_BY_CODE, PLANE_BY_CODE)
from .domain import AIRPORTS, MISSIONS, distance_nm, Phase
from .finance import brl, AIRCRAFT_ECONOMY, estimated_minutes
from .pilot import level_progress
from .planning import inspect_preflight

BG = '#071321'
SURFACE = '#0b1b2b'
CARD = '#112538'
RAISED = '#172e43'
BORDER = '#26475c'
CYAN = '#35d6ff'
CYAN_DARK = '#0b5570'
TEXT = '#eef7ff'
MUTED = '#91aabd'
GOLD = '#f4be4b'
GREEN = '#54d799'
RED = '#ed7a86'
FONT = 'Segoe UI'
ASSETS = Path(__file__).resolve().parent / 'assets'


def safe_coords(m):
    """Coordenadas reais do contrato ou aeroportos conhecidos, nunca inventadas."""
    origin, dest = AIRPORTS.get(m.origin), AIRPORTS.get(m.destination)
    a = (m.origin_lat, m.origin_lon) if None not in (m.origin_lat, m.origin_lon) else (
        (origin.latitude, origin.longitude) if origin else None)
    b = (m.destination_lat, m.destination_lon) if None not in (m.destination_lat, m.destination_lon) else (
        (dest.latitude, dest.longitude) if dest else None)
    return a, b


def normalized_progress(xp):
    return level_progress(max(0, int(xp)))


class DashboardUI:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.market_cache_at = 0
        self.market_cache_center = ''
        self.market_offers = []
        self.map_canvas = None
        self.scroll_canvas = None
        self.mission_key = None
        self.pilot_text = StringVar(value='Cadastre seu piloto')
        self.pilot_subtext = StringVar(value='Autônomo')
        self.xp_title = StringVar(value='NÍVEL —')
        self.connection = StringVar(value='SIMCONNECT OFFLINE')
        self.aircraft_title = StringVar(value='Nenhuma aeronave selecionada')
        self.aircraft_ref = StringVar(value='')
        self.airport = StringVar(value='—')
        self.condition = StringVar(value='—')
        self.fuel_amount = StringVar(value='—')
        self.fuel_mode_label = StringVar(value='CONTROLE ATIVO')
        self.mission_route = StringVar(value='SEM CONTRATO ATIVO')
        self.mission_title = StringVar(value='Aceite uma missão para começar.')
        self.mission_pay = StringVar(value='—')
        self.mission_bonus = StringVar(value='—')
        self.flight_summary = StringVar(value='Nenhum despacho ativo.')
        self.wind_origin = StringVar(value='METAR não integrado')
        self.wind_dest = StringVar(value='METAR não integrado')
        self.realmode_label = StringVar(value='Abra o despacho para marcar as opções pré-voo.')
        self.market_airport = StringVar(value='Configure base ICAO ou conecte ao MSFS')
        self.career_flights = StringVar(value='0')
        self.career_hours = StringVar(value='0 h')
        self.career_qualifications = StringVar(value='—')
        self.images = {}
        self.market_buttons = []
        self.nav_buttons = {}
        self.selected_nav = 'Dashboard'
        self._last_refresh = 0
        self._last_market_refresh = 0
        self.realism_items = {}
        self.aircraft_photo = None
        self.phase_badge = StringVar(value='—')
        self.fuel_btn = None

    @staticmethod
    def text(parent, text=None, size=10, color=TEXT, bold=False, bg=None,
             anchor='w', wraplength=0, var=None, **kwargs):
        options = {'textvariable':var} if var is not None else {'text':text or ''}
        return Label(parent, bg=bg or parent.cget('bg'), fg=color,
                     font=(FONT, size, 'bold' if bold else 'normal'),
                     anchor=anchor, wraplength=wraplength, **options, **kwargs)

    @staticmethod
    def card(parent, pad=11, bg=SURFACE):
        return Frame(parent, bg=bg, padx=pad, pady=pad,
                     highlightbackground=BORDER, highlightthickness=1)

    def button(self, parent, name, callback, accent=False, size=9, pady=10,
               bg=None, fg=None):
        col = bg or (CYAN if accent else RAISED)
        foreground = fg or (BG if accent else TEXT)
        b=Button(parent,text=name,command=callback,bg=col,fg=foreground,
                 font=(FONT,size,'bold'),bd=0,relief='flat',padx=12,pady=pady,
                 cursor='hand2',highlightthickness=0,activebackground=(GOLD if accent else '#28506b'),
                 activeforeground=BG if accent else TEXT)
        return b

    def photo(self, name, desired_w, desired_h):
        """PNG embutido, sem dependência PIL no computador do jogador."""
        name = name if name.endswith('.png') else name + '.png'
        key = (name, desired_w, desired_h)
        if key not in self.images:
            try:
                raw = PhotoImage(file=str(ASSETS/name))
                self.images[key] = raw.subsample(3 if name=='cessna_152_concept.png' else 2 if name=='sidebar_sunset.png' else 1)
            except Exception:
                self.images[key] = None
        return self.images[key]

    def header(self):
        root=self.root
        header=Frame(root,bg=BG,height=91)
        header.pack(fill='x')
        header.pack_propagate(False)
        title=Frame(header,bg=BG)
        title.pack(side='left',padx=(21,16),fill='y')
        line=Frame(title,bg=BG)
        line.pack(anchor='w',pady=(13,0))
        self.text(line,'✈',25,CYAN,True).pack(side='left',padx=(0,7))
        self.text(line,'FLIGHTSIM',18,TEXT,True).pack(side='left')
        self.text(line,'CARREIRA',18,CYAN,True).pack(side='left')
        self.text(title,'SISTEMA DE CARREIRA PARA MSFS 2020',8,MUTED).pack(anchor='w')
        right=Frame(header,bg=BG)
        right.pack(side='right',fill='y',padx=(0,13))
        self.button(right,'✕',self.app._close,size=14,pady=6).pack(side='right',padx=3)
        self.button(right,'—',self.root.iconify,size=13,pady=6).pack(side='right',padx=3)
        self.button(right,'⚙',self.open_settings,size=14,pady=6).pack(side='right',padx=3)
        status=Frame(right,bg=SURFACE,padx=12,pady=13,highlightbackground=BORDER,highlightthickness=1)
        status.pack(side='right',padx=5,pady=14)
        self.text(status,var=self.connection,size=9,color=GREEN,bold=True,bg=SURFACE).pack()
        money=Frame(right,bg=SURFACE,padx=16,pady=8,highlightbackground=BORDER,highlightthickness=1)
        money.pack(side='right',padx=8,pady=13)
        self.text(money,'CAIXA DA CARREIRA',8,MUTED,bg=SURFACE).pack(anchor='e')
        self.text(money,var=self.app.balance_var,size=17,color=GOLD,bold=True,bg=SURFACE).pack(anchor='e')
        level=Frame(right,bg=BG,padx=6)
        level.pack(side='right',padx=5,pady=13)
        self.text(level,var=self.xp_title,size=11,color=CYAN,bold=True).pack(anchor='w')
        self.app.level_bar=self.app._progress_meter(level,self.app.level_fraction,width=160,height=7)
        self.app.level_bar.pack(fill='x',pady=8)
        ident=Frame(right,bg=BG)
        ident.pack(side='right',padx=(0,9),pady=12)
        self.text(ident,var=self.pilot_text,size=11,bold=True).pack(anchor='w')
        self.text(ident,var=self.pilot_subtext,size=9,color=MUTED).pack(anchor='w')
        Frame(root,bg=BORDER,height=1).pack(fill='x')

    def sidebar(self,parent):
        side=Frame(parent,bg='#071827',width=197)
        side.pack(side='left',fill='y',padx=(0,8))
        side.pack_propagate(False)
        title=self.card(side,pad=12)
        title.pack(fill='x',padx=8,pady=(12,9))
        self.text(title,'FLIGHTSIMCARREIRA',10,CYAN,True,bg=SURFACE).pack(anchor='w')
        self.text(title,'OPS CENTER  /  ALPHA',8,MUTED,bg=SURFACE).pack(anchor='w',pady=(4,0))
        self.text(side,'OPERAÇÕES',8,GOLD,True,bg='#071827').pack(anchor='w',padx=15,pady=(9,5))
        menu=[('⌂','Dashboard',lambda:self.activate('Dashboard')),
              ('✈','Missões e Contratos',self.app._market_window),
              ('◎','Mercado Regional',self.app._market_window),
              ('▣','Frota / Hangar',self.app._fleet_window),
              ('◈','Planejamento de Voo',self.app._planning_window),
              ('♙','Meu Piloto',self.app._pilot_window),
              ('▥','Finanças',self.app._finance_window),
              ('▤','Companhias',self.app._employment_window),
              ('≡','Logbook',self.open_logbook),
              ('▥','Análise e Relatórios',self.open_reports),
              ('⚙','Configurações',self.open_settings)]
        for ico,name,action in menu:
            b=self.button(side,f'{ico}   {name}',action,size=9,pady=10,
                          bg=(CYAN_DARK if name=='Dashboard' else '#0b2235'),fg=TEXT)
            b.configure(anchor='w')
            b.pack(fill='x',padx=8,pady=2)
            self.nav_buttons[name]=b
        Frame(side,bg='#071827').pack(fill='both',expand=True)
        # Artwork approved with the concept, decorative only (not a chart).
        sunset=self.photo('sidebar_sunset',320,370)
        if sunset:
            Label(side,image=sunset,bg='#071827',bd=0).pack(fill='x',padx=8,pady=(0,6))
        else:
            self.text(side,'VOE. APRENDA. EVOLUA.',9,CYAN,True).pack(padx=8,pady=12)

    def activate(self,name):
        self.selected_nav=name
        for label,b in self.nav_buttons.items():
            b.configure(bg=CYAN_DARK if label==name else '#0b2235')

    def build(self):
        self.root.title('FlightSimCarreira  •  Midnight Ops  |  v0.6.2 Alpha.1')
        self.root.geometry('1580x920')
        self.root.minsize(1280,750)
        self.root.configure(bg=BG)
        self.header()
        wrapper=Frame(self.root,bg=BG)
        wrapper.pack(fill='both',expand=True,padx=(3,11),pady=(7,3))
        self.sidebar(wrapper)
        holder=Frame(wrapper,bg=BG)
        holder.pack(side='left',fill='both',expand=True)
        self.scroll_canvas=Canvas(holder,bg=BG,bd=0,highlightthickness=0)
        scrollbar=Scrollbar(holder,orient='vertical',command=self.scroll_canvas.yview)
        scrollbar.pack(side='right',fill='y')
        self.scroll_canvas.pack(side='left',fill='both',expand=True)
        self.scroll_canvas.configure(yscrollcommand=scrollbar.set)
        content=Frame(self.scroll_canvas,bg=BG)
        item=self.scroll_canvas.create_window((0,0),window=content,anchor='nw')
        content.bind('<Configure>',lambda e:self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox('all')))
        self.scroll_canvas.bind('<Configure>',lambda e:self.scroll_canvas.itemconfigure(item,width=e.width))
        self.scroll_canvas.bind('<MouseWheel>',lambda e:self.scroll_canvas.yview_scroll(-int(e.delta/120),'units'))
        content.grid_columnconfigure(0,minsize=248,weight=0)
        content.grid_columnconfigure(1,minsize=545,weight=1)
        content.grid_columnconfigure(2,minsize=258,weight=0)
        self.left_column(content)
        self.center_column(content)
        self.right_column(content)
        # Widget oculto para preservar o contrato de API do diário legado.
        self.app.mission_select=ttk.Combobox(self.root, state='readonly', values=[
            f'{m.origin} → {m.destination} | {brl(m.reward)} | {m.title}' for m in MISSIONS])
        self.app.mission_select.current(0)
        self.app.history_text=Text(self.root,bd=0,height=1)  # suporte à API do logbook legada
        self.app._refresh_history()
        self.refresh(force_market=True)

    def left_column(self,main):
        col=Frame(main,bg=BG)
        col.grid(row=0,column=0,sticky='nsew',padx=(0,6),pady=5)
        market=self.card(col,pad=11)
        market.pack(fill='x',pady=(0,9))
        self.text(market,'MERCADO REGIONAL',11,GOLD,True,bg=SURFACE).pack(anchor='w')
        self.text(market,var=self.market_airport,size=9,color=MUTED,bg=SURFACE,wraplength=218).pack(anchor='w',pady=(4,9))
        self.market_rows=Frame(market,bg=SURFACE)
        self.market_rows.pack(fill='x')
        self.button(market,'⌕  Ver todas as missões',self.app._market_window,accent=True).pack(fill='x',pady=(8,1))
        career=self.card(col,pad=12)
        career.pack(fill='x')
        self.text(career,'RESUMO DA CARREIRA',10,GOLD,True,bg=SURFACE).pack(anchor='w',pady=(0,10))
        for label,var in [('Voos concluídos',self.career_flights),('Horas de voo',self.career_hours),
                          ('Habilitações',self.career_qualifications),('Saldo atual',self.app.balance_var)]:
            row=Frame(career,bg=SURFACE)
            row.pack(fill='x',pady=5)
            self.text(row,label,9,MUTED,bg=SURFACE).pack(side='left')
            self.text(row,var=var,size=10,color=GOLD if label=='Saldo atual' else TEXT,
                      bold=True,bg=SURFACE).pack(side='right')
        self.text(career,'EVOLUÇÃO DO PILOTO',8,MUTED,True,bg=SURFACE).pack(anchor='w',pady=(10,4))
        self.left_xp_bar=Canvas(career,bg=SURFACE,height=8,highlightthickness=0)
        self.left_xp_bar.pack(fill='x')
        self.left_xp_bar.bind('<Configure>',lambda e:self._draw_fraction(self.left_xp_bar,self.app.level_fraction))
        self.button(career,'Ver meu piloto',self.app._pilot_window).pack(fill='x',pady=(12,0))

    def center_column(self,main):
        col=Frame(main,bg=BG)
        col.grid(row=0,column=1,sticky='nsew',padx=5,pady=5)
        contract=self.card(col,pad=12)
        contract.pack(fill='x',pady=(0,8))
        self.text(contract,'▣  CONTRATO ATIVO',11,CYAN,True,bg=SURFACE).pack(anchor='w')
        line=Frame(contract,bg=SURFACE)
        line.pack(fill='x',pady=(9,0))
        text=Frame(line,bg=SURFACE)
        text.pack(side='left',fill='x',expand=True)
        self.text(text,var=self.mission_route,size=19,bold=True,bg=SURFACE).pack(anchor='w')
        self.text(text,var=self.mission_title,size=10,color=MUTED,bg=SURFACE).pack(anchor='w')
        prices=Frame(line,bg=SURFACE)
        prices.pack(side='right')
        self.text(prices,'PAGAMENTO BRUTO',8,MUTED,bg=SURFACE).pack(anchor='e')
        self.text(prices,var=self.mission_pay,size=17,color=GOLD,bold=True,bg=SURFACE).pack(anchor='e')
        self.text(prices,var=self.mission_bonus,size=9,color=GREEN,bg=SURFACE).pack(anchor='e')
        mapbox=self.card(col,pad=8)
        mapbox.pack(fill='x',pady=(0,8))
        top=Frame(mapbox,bg=SURFACE)
        top.pack(fill='x',pady=(1,6))
        self.text(top,'MAPA E TRAJETO',11,GOLD,True,bg=SURFACE).pack(side='left')
        self.text(top,'ESQUEMÁTICO · SEM CARTA VFR',8,MUTED,bg=SURFACE).pack(side='right')
        self.map_canvas=Canvas(mapbox,bg='#081b2a',height=284,bd=0,highlightthickness=0)
        self.map_canvas.pack(fill='x')
        self.map_canvas.bind('<Configure>',lambda e:self.redraw_map())
        tabs=Frame(mapbox,bg=SURFACE)
        tabs.pack(fill='x',pady=(7,0))
        for text,fn in [('Mapa e rota',self.app._prepare_active_plan),
                        ('METAR / Clima',self.open_weather),
                        ('Pistas / Luzes',self.app._planning_window),
                        ('Peso / Balanceamento',self.app._planning_window),
                        ('Plano VFR',self.app._prepare_active_plan)]:
            self.button(tabs,text,fn,accent=text=='Mapa e rota',size=8,pady=7).pack(side='left',padx=(0,4))
        telemetry=self.card(col,pad=9)
        telemetry.pack(fill='x',pady=(0,8))
        self.text(telemetry,'◉  TELEMETRIA AO VIVO',10,CYAN,True,bg=SURFACE).pack(anchor='w',pady=(0,7))
        metrics=Frame(telemetry,bg=SURFACE)
        metrics.pack(fill='x')
        for i,(key,title,unit) in enumerate([
            ('ias','IAS','kt'),('gs','SOLO','kt'),('alt','ALTITUDE','ft'),
            ('agl','AGL','ft'),('vs','VERTICAL','ft/min'),('phase','FASE','')]):
            box=Frame(metrics,bg=CARD,padx=5,pady=8,highlightbackground=BORDER,highlightthickness=1)
            box.grid(row=0,column=i,sticky='nsew',padx=(0 if i==0 else 3,0))
            metrics.grid_columnconfigure(i,weight=1,uniform='telemetry')
            self.text(box,title,8,MUTED,True,bg=CARD,anchor='center').pack(fill='x')
            value=self.phase_badge if key=='phase' else self.app.flight_vars[key]
            self.text(box,var=value,size=14,color=GREEN if key=='phase' else TEXT,
                      bold=True,bg=CARD,anchor='center').pack(fill='x',pady=(4,1))
            self.text(box,unit or ' ',7,MUTED,bg=CARD,anchor='center').pack(fill='x')
        metar=Frame(col,bg=BG)
        metar.pack(fill='x',pady=(0,8))
        for title,var in [('METAR ORIGEM',self.wind_origin),('METAR DESTINO',self.wind_dest)]:
            pane=self.card(metar,pad=10)
            pane.pack(side='left',fill='both',expand=True,padx=(0,4) if title=='METAR ORIGEM' else (4,0))
            self.text(pane,title,9,CYAN,True,bg=SURFACE).pack(anchor='w')
            self.text(pane,var=var,size=9,color=MUTED,bg=SURFACE,wraplength=250).pack(anchor='w',pady=(5,0))
        bottom=Frame(col,bg=BG)
        bottom.pack(fill='both',expand=True)
        log=self.card(bottom,pad=10)
        log.pack(side='left',fill='both',expand=True,padx=(0,4))
        self.text(log,'REGISTRO DO VOO',10,GOLD,True,bg=SURFACE).pack(anchor='w')
        self.app.log_text=Text(log,bg='#071522',fg='#c6d7e4',height=8,
                              font=('Consolas',9),bd=0,relief='flat',wrap='word',
                              padx=7,pady=7,insertbackground=CYAN,state='disabled')
        self.app.log_text.pack(fill='both',expand=True,pady=(6,0))
        bonus=self.card(bottom,pad=10)
        bonus.pack(side='left',fill='both',expand=True,padx=(4,0))
        self.text(bonus,'BÔNUS DE REALISMO',10,GOLD,True,bg=SURFACE).pack(anchor='w')
        self.text(bonus,var=self.realmode_label,size=9,color=GREEN,bg=SURFACE,
                  wraplength=236,justify='left').pack(anchor='w',pady=(7,8))
        for label,key in [('Clima ao vivo','real_weather_declared'),('Horário real','real_time_declared'),
                          ('Assistências realistas','assists_realistic_declared'),('Pistas e iluminação','runway_checked'),
                          ('Rota revisada','route_checked'),('Combustível e reserva','fuel_checked'),
                          ('Peso verificado','payload_checked')]:
            # A edição real continua em Despacho, que valida e persiste os critérios.
            var=StringVar(value='□')
            row=Frame(bonus,bg=SURFACE)
            row.pack(fill='x',pady=1)
            self.text(row,var=var,size=9,color=GREEN,bg=SURFACE).pack(side='left')
            self.text(row,' '+label,size=8,color=TEXT,bg=SURFACE).pack(side='left')
            self.realism_items[key]=var
        self.button(bonus,'Editar antes de decolar',self.app._planning_window,accent=True,size=8,pady=7).pack(fill='x',pady=(9,0))

    def right_column(self,main):
        col=Frame(main,bg=BG)
        col.grid(row=0,column=2,sticky='nsew',padx=(6,0),pady=5)
        aircraft=self.card(col,pad=11)
        aircraft.pack(fill='x',pady=(0,9))
        self.text(aircraft,'AERONAVE EM USO',11,GOLD,True,bg=SURFACE).pack(anchor='w',pady=(0,8))
        art=self.photo('cessna_152_concept',660,245)
        self.aircraft_photo=Label(aircraft,image=art if art else None,text='' if art else 'Imagem ilustrativa',
                                  bg='#0b2233',fg=MUTED,bd=0,height=85 if art else 7)
        self.aircraft_photo.pack(fill='x')
        self.text(aircraft,var=self.aircraft_title,size=15,color=TEXT,bold=True,bg=SURFACE,
                  wraplength=228).pack(anchor='w',pady=(9,2))
        self.text(aircraft,var=self.aircraft_ref,size=8,color=MUTED,bg=SURFACE).pack(anchor='w')
        for name,var in [('Localização',self.airport),('Estado da aeronave',self.condition),
                         ('Combustível',self.fuel_amount)]:
            row=Frame(aircraft,bg=SURFACE)
            row.pack(fill='x',pady=(12,0))
            self.text(row,name,9,MUTED,bg=SURFACE).pack(side='left')
            self.text(row,var=var,size=9,color=TEXT,bold=True,bg=SURFACE).pack(side='right')
        self.fuel_bar=Canvas(aircraft,bg=SURFACE,height=8,highlightthickness=0)
        self.fuel_bar.pack(fill='x',pady=(8,8))
        self.fuel_bar.bind('<Configure>',lambda e:self._draw_fraction(self.fuel_bar,self.fuel_fraction, GREEN))
        self.fuel_fraction=0.0
        self.fuel_btn=self.button(aircraft,'CONTROLE DE COMBUSTÍVEL: ATIVO',self.toggle_fuel,
                                  bg='#103a34',fg=GREEN,size=9,pady=10)
        self.fuel_btn.pack(fill='x',pady=(7,10))
        row=Frame(aircraft,bg=SURFACE)
        row.pack(fill='x')
        self.button(row,'Abastecer',self.refuel_selected,accent=True,pady=10).pack(side='left',fill='x',expand=True,padx=(0,4))
        self.button(row,'Revisar',self.service_selected,pady=10).pack(side='left',fill='x',expand=True,padx=(4,0))
        actions=self.card(col,pad=11)
        actions.pack(fill='x',pady=(0,9))
        self.button(actions,'✈  Preparar voo / Despacho',self.app._planning_window,accent=True,size=10,pady=14).pack(fill='x',pady=(0,9))
        self.button(actions,'⇩  Carregar plano VFR no MSFS',self.app._prepare_active_plan,size=9,pady=12).pack(fill='x')
        extras=self.card(col,pad=11)
        extras.pack(fill='x')
        self.text(extras,'RESUMO DO VOO',10,GOLD,True,bg=SURFACE).pack(anchor='w')
        self.text(extras,var=self.flight_summary,size=9,color=MUTED,bg=SURFACE,
                  wraplength=234,justify='left').pack(anchor='w',pady=(8,12))
        self.button(extras,'Ver frota completa',self.app._fleet_window).pack(fill='x')
        self.button(extras,'Vagas e companhias',self.app._employment_window).pack(fill='x',pady=(8,0))

    def _draw_fraction(self,canvas,fraction,color=CYAN):
        if not canvas.winfo_exists():return
        w=max(10,canvas.winfo_width());h=max(1,canvas.winfo_height())
        canvas.delete('all')
        canvas.create_rectangle(0,0,w,h,fill='#284155',outline='')
        canvas.create_rectangle(0,0,round(w*max(0,min(1,fraction))),h,fill=color,outline='')

    def _region(self):
        a=self.app
        if a.airport_catalog is None:a.airport_catalog=AirportCatalog()
        c=a.airport_catalog
        s=a.last_sample if a.connected else None
        current=c.nearest(s.latitude,s.longitude,6) if s else None
        if current is None:
            p=a.storage.get_pilot()
            current=c.locations.get(p['home_icao']) if p else None
        return current

    def update_market(self,force=False):
        a=self.app
        if not a.storage.get_pilot():
            self.market_airport.set('Cadastre piloto para gerar ofertas locais')
            self.market_offers=[]
        else:
            center=self._region()
            if center is None:
                self.market_airport.set('Sem aeroporto próximo / base não encontrada')
                self.market_offers=[]
            else:
                self.market_airport.set(f'{center.icao}  ·  {center.name}')
                if not force and self.market_cache_center==center.icao and time()-self.market_cache_at<60:
                    return
                now=time(); day=int(now//86400)
                if not a.storage.offer_cache_valid(center.icao,now):
                    offers=generate_offers(center,a.airport_catalog,a.storage.pilot_stats(),
                        a.storage.owned_qualifications(),a.storage.family_experience(),day)
                    emp=a.storage.employment_state()
                    if emp['mode']=='empregado':
                        from .employment import generate_employer_routes
                        offers+=generate_employer_routes(emp['employer_code'],center,a.airport_catalog,
                            a.storage.pilot_stats(),a.storage.owned_qualifications(),a.storage.family_experience(),day)
                    a.storage.save_offers(center.icao,offers,now=now,valid_s=(day+1)*86400-now)
                self.market_offers=[]
                for offer in a.storage.active_offers(center.icao,now):
                    ok,_=eligibility(offer,a.storage.pilot_stats(),a.storage.owned_qualifications(),a.storage.family_experience())
                    if ok:self.market_offers.append(offer)
                self.market_cache_center=center.icao
                self.market_cache_at=now
        for w in self.market_rows.winfo_children():w.destroy()
        for offer in self.market_offers[:5]:
            row=Frame(self.market_rows,bg=CARD,highlightbackground=BORDER,highlightthickness=1)
            row.pack(fill='x',pady=(0,5))
            description=Frame(row,bg=CARD)
            description.pack(side='left',fill='x',expand=True,padx=8,pady=8)
            kind=TYPE_BY_CODE.get(offer.category)
            name=kind.title if kind else offer.title
            if offer.freelance:name+=' · freelancer'
            self.text(description,name,size=9,color=TEXT,bold=True,bg=CARD,wraplength=145).pack(anchor='w')
            self.text(description,f'{offer.origin} → {offer.destination}',size=8,color=MUTED,bg=CARD).pack(anchor='w',pady=(3,0))
            price=Frame(row,bg=CARD)
            price.pack(side='right',padx=7)
            self.text(price,brl(offer.reward),size=9,color=GOLD,bold=True,bg=CARD).pack(anchor='e')
            try:
                mins=estimated_minutes(distance_nm(offer.origin_lat,offer.origin_lon,
                    offer.destination_lat,offer.destination_lon))
                self.text(price,f'~{mins} min',size=8,color=MUTED,bg=CARD).pack(anchor='e')
            except (TypeError,ValueError): pass
            def inspect_offer(_event, m=offer):
                # Escolha feita na janela de mercado, com todos os detalhes.
                self.app._market_window()
            for el in (row,description,price,*description.winfo_children(),*price.winfo_children()):
                el.bind('<Button-1>',inspect_offer)
        if not self.market_offers:
            self.text(self.market_rows,'Nenhuma proposta elegível por enquanto.\nAbra o mercado para conferir.',
                      size=9,color=MUTED,bg=SURFACE,wraplength=200,justify='left').pack(pady=12)

    def refresh(self,force_market=False):
        """Atualização leve; é chamada no loop Tk, nunca de uma thread SimConnect."""
        a=self.app
        p=a.storage.get_pilot()
        stats=a.storage.pilot_stats() if p else {'xp':0,'hours':0,'flights':0,'qualifications':set(),'level':1}
        self.pilot_text.set(p['callsign'] if p else 'PILOTO NÃO CADASTRADO')
        mode=a.storage.employment_state()['mode'] if p else 'autonomo'
        self.pilot_subtext.set({'autonomo':'Piloto autônomo','empregado':'Piloto contratado','empresario':'Empresa própria'}.get(mode,mode))
        self.xp_title.set('NÍVEL '+str(stats['level']))
        self.career_flights.set(str(stats['flights']))
        self.career_hours.set(f"{stats['hours']:.1f} h")
        self.career_qualifications.set(', '.join(sorted(stats['qualifications'])) or '—')
        self.connection.set('● SIMCONNECT ATIVO' if a.connected and a.mode=='MSFS' else
                            ('● DEMONSTRAÇÃO' if a.mode=='Demo' else '● DESCONECTADO'))
        self.app.balance_var.set(brl(int(a.storage.get_setting('balance') or a.career.balance)))
        self._draw_fraction(self.left_xp_bar,a.level_fraction)
        m=a.career.mission
        mission_id=m.id if m else None
        if m:
            self.mission_route.set(f'{m.origin}  →  {m.destination}')
            self.mission_title.set(m.title + (' · FREELANCER' if m.freelance else ''))
            self.mission_pay.set(brl(m.reward))
        else:
            self.mission_route.set('SEM CONTRATO ATIVO')
            self.mission_title.set('Escolha uma proposta no mercado regional.')
            self.mission_pay.set('—')
        plan=a._saved_preflight() if m else None
        if plan and m:
            for k,v in self.realism_items.items():v.set('☑' if getattr(plan,k,False) else '□')
            try:
                inspected=inspect_preflight(m,plan)
                pct=round(inspected['bonus_fraction']*100,1)
                self.mission_bonus.set(f'Bônus previsto: +{pct:g}%')
                self.realmode_label.set(f'Previsto: +{pct:g}% · congelado na decolagem. Declarações não validadas automaticamente.')
                mins=inspected['minutes']
                dist=inspected['distance_nm']
                self.flight_summary.set(f"Distância: {dist if dist is not None else '—'} NM\nTempo estimado: {mins or '—'} min\nAltitude: {plan.altitude_ft} ft\nChecklist salvo para este contrato.")
            except (ValueError,KeyError,TypeError):
                self.mission_bonus.set('Despacho incompleto')
                self.realmode_label.set('Revise o despacho antes de decolar.')
                self.flight_summary.set('Despacho inválido. Abra Planejamento de Voo.')
        else:
            self.mission_bonus.set('Bônus não configurado' if m else '—')
            self.realmode_label.set('Abra o despacho para editar os critérios pré-voo.')
            for v in self.realism_items.values():v.set('□')
            if m:
                coords=safe_coords(m)
                dist=distance_nm(*coords[0],*coords[1]) if all(coords) else None
                self.flight_summary.set(f"{m.origin} → {m.destination}\nDistância: {dist:.1f} NM" if dist else 'Rota sem coordenadas disponíveis')
            else:self.flight_summary.set('Nenhum voo planejado. Aceite uma missão para iniciar.')
        fm=a.storage.fleet_manager()
        selected=fm.selected()
        current=a.last_sample if a.connected else None
        model=(current.aircraft_title if current and current.aircraft_title else None)
        name=selected['title'] if selected else (model or 'Nenhuma aeronave própria selecionada')
        self.aircraft_title.set(name)
        self.aircraft_ref.set(selected['ref'] if selected else 'Modelo carregado no MSFS' if model else '')
        self.aircraft_photo.configure(text='Arte ilustrativa · Cessna 152' if selected and selected['code']=='c152' else 'Imagem ilustrativa do Cessna 152 · sem foto do modelo atual' if selected and selected['code']!='c152' else 'Arte ilustrativa · Cessna 152', compound='top', fg=MUTED, font=(FONT,7))
        self.airport.set(selected['airport'] if selected else '—')
        self.condition.set(f"{selected['condition']:.1f}%" if selected else '—')
        fuel=current.fuel_gallons if current and current.fuel_gallons is not None else None
        self.fuel_amount.set(f'{fuel:.1f} gal' if fuel is not None else '—')
        self.phase_badge.set({'aguardando':'AGUARD.', 'em voo':'EM VOO', 'solo':'SOLO', 'pousado':'POUSADO'}.get(a.tracker.phase.value,a.tracker.phase.value.upper()))
        model_econ=AIRCRAFT_ECONOMY.get(selected['code']) if selected else None
        self.fuel_fraction=min(1,max(0,fuel/model_econ.fuel_capacity_gal)) if fuel is not None and model_econ else 0
        self._draw_fraction(self.fuel_bar,self.fuel_fraction,GREEN)
        enabled=a.storage.get_setting('fuel_control_enabled')!='0'
        self.fuel_btn.configure(text='CONTROLE DE COMBUSTÍVEL: '+('ATIVO' if enabled else 'DESLIGADO  (−30%)'),
                                bg='#103a34' if enabled else '#5f332e',fg=GREEN if enabled else GOLD)
        s=a.last_sample if a.connected else None
        self.wind_origin.set(('Vento local (SimConnect): '+f'{s.wind_kt:.0f} kt' if s.wind_kt is not None else 'METAR não integrado') if s else 'METAR não integrado')
        self.wind_dest.set('METAR não integrado • sem consulta online nesta fase')
        if force_market or time()-self.market_cache_at>60 or self.market_cache_center!=(self._region().icao if p and self._region() else ''):
            self.update_market(force=force_market)
        if mission_id!=self.mission_key or (time()-self._last_refresh)>2:
            self.redraw_map()
            self.mission_key=mission_id
        self._last_refresh=time()

    def redraw_map(self):
        c=self.map_canvas
        if not c or not c.winfo_exists():return
        c.delete('all')
        w=max(480,c.winfo_width());h=max(240,c.winfo_height())
        c.create_rectangle(0,0,w,h,fill='#081b2a',outline='')
        # Grid ornamental, sem informações aeronáuticas inventadas.
        for x in range(0,w,44):c.create_line(x,0,x,h,fill='#112d42',width=1)
        for y in range(0,h,34):c.create_line(0,y,w,y,fill='#112d42',width=1)
        for k in range(6):
            c.create_line([(x,max(8,min(h-8,h*(.19+k*.115)+16*__import__('math').sin((x+k*37)/74))))
                           for x in range(0,w+6,6)],fill='#103449',smooth=True,width=1)
        m=self.app.career.mission
        if not m:
            c.create_text(w/2,h/2-10,text='AGUARDANDO MISSÃO',fill='#9ac1d3',font=(FONT,16,'bold'))
            c.create_text(w/2,h/2+20,text='Selecione um contrato para mostrar sua rota',fill=MUTED,font=(FONT,10))
            return
        a,b=safe_coords(m)
        if not a or not b or not all(isfinite(v) for v in (*a,*b)):
            c.create_text(w/2,h/2,text='COORDENADAS DO CONTRATO INDISPONÍVEIS',fill=MUTED,font=(FONT,10))
            return
        # Ajusta a projeção ao retângulo do trajeto, incluindo a posição se relevante.
        latmin=min(a[0],b[0])-.025;latmax=max(a[0],b[0])+.025
        lonmin=min(a[1],b[1])-.025;lonmax=max(a[1],b[1])+.025
        def project(lat,lon):
            return (44+(lon-lonmin)/(lonmax-lonmin)*(w-88),
                    h-40-(lat-latmin)/(latmax-latmin)*(h-80))
        ax,ay=project(*a);bx,by=project(*b)
        c.create_line(ax,ay,bx,by,fill='#0e7895',width=7)
        c.create_line(ax,ay,bx,by,fill=CYAN,width=3)
        for x,y,label in [(ax,ay,m.origin),(bx,by,m.destination)]:
            c.create_oval(x-11,y-11,x+11,y+11,fill='#0c3d52',outline='#87e9ff',width=2)
            c.create_oval(x-4,y-4,x+4,y+4,fill=CYAN,outline='')
            py=y-31 if y>60 else y+30
            c.create_text(x,py,text=label,fill=TEXT,font=(FONT,12,'bold'))
        s=self.app.last_sample if self.app.connected else None
        if s and latmin<=s.latitude<=latmax and lonmin<=s.longitude<=lonmax:
            px,py=project(s.latitude,s.longitude)
            c.create_oval(px-12,py-12,px+12,py+12,outline=GOLD,width=2)
            c.create_text(px,py,text='✈',fill=TEXT,font=(FONT,18,'bold'))
        c.create_text(w-12,h-13,text='TRÁFEGO ONLINE / MAPA SATÉLITE: ETAPA FUTURA',
                      anchor='e',fill='#678a9d',font=(FONT,8))

    def toggle_fuel(self):
        a=self.app
        if a.tracker.phase==Phase.AIRBORNE:
            messagebox.showwarning('Combustível','Altere o modo somente em solo. A configuração é congelada na decolagem.')
            return
        current=a.storage.get_setting('fuel_control_enabled')!='0'
        next_enabled=not current
        if not next_enabled and not messagebox.askyesno('Desligar controle de combustível',
             'Desligar o controle pelo FlightSimCarreira?\n\nIsso reduzirá o dinheiro e o XP dos próximos voos em 30%.'):
            return
        a.storage.set_setting('fuel_control_enabled','1' if next_enabled else '0')
        a._log('Controle de combustível '+('ATIVADO' if next_enabled else 'DESLIGADO: penalidade -30% R$/XP.'))
        self.refresh()

    def refuel_selected(self):
        """Reutiliza exatamente as regras seguras de abastecimento da Frota."""
        a=self.app
        if not (a.mode=='MSFS' and a.connected and a.last_sample and
                a.last_sample.on_ground and time()-a.last_sample.timestamp<10):
            messagebox.showwarning('Combustível','Conecte o MSFS com a aeronave parada no solo.');return
        chosen=a.storage.fleet_manager().selected()
        if not chosen:
            messagebox.showwarning('Combustível','Selecione primeiro uma aeronave própria/alugada na Frota.');return
        from .contracts import aircraft_model
        if chosen['code']!=aircraft_model(a.last_sample.aircraft_title):
            messagebox.showwarning('Combustível','A aeronave em uso no MSFS deve corresponder à selecionada.');return
        if not messagebox.askyesno('Abastecer aeronave',
            f'Completar os tanques de {chosen["title"]}, descontando do caixa da carreira?'):
            return
        try:
            result=a.fuel_manager.refuel_full(chosen['ref'])
        except (ValueError,KeyError,OSError) as exc:
            messagebox.showwarning('Abastecimento',str(exc));return
        a.career.balance=int(a.storage.get_setting('balance') or 0)
        a.balance_var.set(brl(a.career.balance))
        a._log(f"ABASTECIMENTO: +{result['added_gal']:.1f} gal por {brl(result['cost_brl'])}.")
        self.refresh()

    def service_selected(self):
        a=self.app
        if a.tracker.phase==Phase.AIRBORNE:
            messagebox.showwarning('Manutenção','Faça revisão somente em solo.');return
        chosen=a.storage.fleet_manager().selected()
        if not chosen:
            messagebox.showwarning('Manutenção','Selecione uma aeronave na Frota.');return
        if not messagebox.askyesno('Revisão de aeronave',
            f'Realizar revisão paga de {chosen["title"]}? A operação é virtual no addon.'):
            return
        try:
            a.storage.fleet_manager().service(chosen['ref'])
        except (ValueError,KeyError,OSError) as exc:
            messagebox.showwarning('Manutenção',str(exc));return
        a.career.balance=int(a.storage.get_setting('balance') or 0)
        a.balance_var.set(brl(a.career.balance))
        a._log('MANUTENÇÃO: revisão concluída para '+chosen['title'])
        self.refresh()

    def open_weather(self):
        messagebox.showinfo('METAR / Clima',
            'Nesta fase usamos apenas dados de telemetria que o MSFS já fornece.\n\n'
            'METAR oficial de origem e destino ainda não foi integrado; não serão mostradas condições inventadas.')

    def open_logbook(self):
        win=Toplevel(self.root)
        win.title('FlightSimCarreira • Diário de Bordo')
        win.geometry('750x500');win.configure(bg=BG)
        frame=self.card(win,pad=16);frame.pack(fill='both',expand=True,padx=16,pady=16)
        self.text(frame,'DIÁRIO DE BORDO',15,CYAN,True,bg=SURFACE).pack(anchor='w',pady=(0,12))
        t=Text(frame,bg='#071522',fg=TEXT,font=('Consolas',10),bd=0,padx=12,pady=12,wrap='word')
        t.pack(fill='both',expand=True)
        flights=self.app.storage.list_flights()
        for fid,start,end,touch,stalls,mission,reward in flights:
            t.insert(END,f'VOO #{fid:03}  •  {(end-start)/60:.0f} minutos\n'
                     f'{mission or "Voo livre"}  •  Bruto: {brl(reward)}\n'
                     f'Pouso estimado: {touch:.0f} ft/min\n\n' if touch is not None else
                     f'VOO #{fid:03}  •  {(end-start)/60:.0f} minutos  •  {mission or "Voo livre"}\n')
        if not flights:t.insert(END,'Nenhum voo registrado até agora.')
        t.configure(state='disabled')

    def open_reports(self):
        win=Toplevel(self.root)
        win.title('FlightSimCarreira • Análise segura')
        win.geometry('540x290');win.configure(bg=BG)
        f=self.card(win,pad=20);f.pack(fill='both',expand=True,padx=14,pady=14)
        self.text(f,'ANÁLISE / NEOFLY',14,CYAN,True,bg=SURFACE).pack(anchor='w',pady=(0,14))
        self.button(f,'Localizar arquivos NeoFly',self.app._locate_neofly).pack(fill='x',pady=6)
        self.button(f,'Analisar banco somente leitura',self.app._analyze).pack(fill='x',pady=6)
        self.button(f,'Salvar log de diagnóstico',self.app._save_log).pack(fill='x',pady=6)

    def open_settings(self):
        win=Toplevel(self.root)
        win.title('FlightSimCarreira • Configurações')
        win.geometry('560x380');win.configure(bg=BG)
        f=self.card(win,pad=20);f.pack(fill='both',expand=True,padx=14,pady=14)
        self.text(f,'CONFIGURAÇÕES',15,CYAN,True,bg=SURFACE).pack(anchor='w')
        self.text(f,'Ações atuais e utilitários do projeto.',9,MUTED,bg=SURFACE).pack(anchor='w',pady=(4,15))
        for name,action in [('Conectar MSFS',self.app._connect),('Desconectar',self.app._stop),
                            ('Demo sem MSFS',self.app._demo_start),('Aceitar contrato da demo',lambda:self.app._accept_specific(MISSIONS[0])),('Avançar demo',self.app._demo_next),
                            ('Configurações financeiras e de combustível',self.app._finance_window),
                            ('Salvar log de diagnóstico',self.app._save_log),
                            ('Painel local experimental',self.app._open_local_panel)]:
            self.button(f,name,action,size=9,pady=7).pack(fill='x',pady=2)
