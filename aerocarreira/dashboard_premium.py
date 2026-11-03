"""Midnight Ops v0.6.3: responsive, scroll-free dashboard redesign.

The controller/business logic remains in dashboard_ui.DashboardUI. This file only
replaces its visual shell: every interactive button delegates to the existing
Application method. Missing external map/METAR data is labelled as unavailable.
"""
from __future__ import annotations
import os
from pathlib import Path
from functools import lru_cache
from tkinter import (Canvas, Frame, Label, Text, StringVar, PhotoImage, Toplevel,
                     filedialog, messagebox, ttk)
from time import time

from .dashboard_ui import DashboardUI as BaseUI
from .dashboard_ui import (BG, SURFACE, CARD, BORDER, CYAN, TEXT, MUTED, GOLD,
                           GREEN, RED, FONT, ASSETS, safe_coords)
from .midnight_widgets import GlowBar, GlowButton, roundrect, blend
from .contracts import TYPE_BY_CODE
from .finance import brl, estimated_minutes
from .domain import distance_nm, MISSIONS
from .pilot import level_progress

try:
    from PIL import Image, ImageTk, ImageDraw, ImageOps, ImageEnhance
except ImportError:  # optional: graceful fallback for an interrupted install
    Image=ImageTk=ImageDraw=ImageOps=ImageEnhance=None

MID_BG='#061321'
MID_PANEL='#091c2b'
MID_CARD='#0e2538'
MID_MUTED='#aac2d0'
MID_BORDER='#1c4862'


def nationality_from_base(icao: str, lookup=None) -> str:
    """Return ISO country for the ICAO home base, not the pilot's actual citizenship.

    Never infer nationality from pilot name or callsign. If a global catalog is
    unavailable, fallback only for ICAOs whose Brazilian prefixes are known.
    """
    code=(icao or '').strip().upper()
    if len(code)!=4 or not code.isalpha():return ''
    if lookup:
        data=lookup(code)
        if data:return str(data).upper()[:2]
    try:
        import airportsdata
        item=_airport_country_catalog().get(code)
        country=item.get('country') if item else None
        if isinstance(country,str) and len(country)==2:return country.upper()
    except (ImportError,ValueError,KeyError,OSError):pass
    if code[:2] in {'SB','SD','SI','SJ','SN','SS','SW'}:return 'BR'
    return ''


@lru_cache(maxsize=1)
def _airport_country_catalog():
    try:
        import airportsdata
        return airportsdata.load('ICAO')
    except (ImportError,ValueError,OSError,KeyError):
        return {}


def local_avatar_path(base_dir):
    return Path(base_dir)/'pilot_avatar.png'


def gradient_image(path, w, h, *, soft_corner=10, darken=.18, bottom_fade=True):
    """Blend decorative photo into card; avoid visually floating PNG rectangles."""
    if not Image or not Path(path).exists() or w<2 or h<2:return None
    with Image.open(path) as src:
        pic=ImageOps.fit(src.convert('RGB'),(int(w),int(h)),method=Image.Resampling.LANCZOS)
    if darken:pic=ImageEnhance.Brightness(pic).enhance(1-darken)
    pic=pic.convert('RGBA')
    if bottom_fade:
        overlay=Image.new('RGBA',pic.size,(0,0,0,0));d=ImageDraw.Draw(overlay)
        for y in range(h):
            p=y/max(1,h-1)
            if p>.4:d.line((0,y,w,y),fill=(4,17,28,round(195*((p-.4)/.6)**1.45)))
        pic=Image.alpha_composite(pic,overlay)
    if soft_corner:
        mask=Image.new('L',(w,h),0)
        ImageDraw.Draw(mask).rounded_rectangle((0,0,w-1,h-1),radius=soft_corner,fill=255)
        pic.putalpha(mask)
    return ImageTk.PhotoImage(pic)


def level_to_rank(level, qualifications):
    # A design/rank marker, not a real pilot's qualification.
    quals=set(qualifications or ())
    for code,title in [('PLA','LINHA AÉREA'),('MLTE','MULTIMOTOR'),('IFR','INSTRUMENTOS'),('PCA','COMERCIAL'),('PPA','PRIVADO')]:
        if code in quals:return code, title
    return '—','PILOTO EM FORMAÇÃO'


class DashboardUI(BaseUI):
    def __init__(self,app):
        super().__init__(app)
        self.theme_scale=1.0
        self.bars=[]
        self.window_fit={'width':0,'height':0}
        self.header_flag=StringVar(value='—')
        self.iso_country=''
        self.rank_code='—'
        self.rank_level=1
        self.header_rank=StringVar(value='PPA')
        self.header_xp_detail=StringVar(value='')
        self.career_reputation=StringVar(value='—')
        self.career_bonus=StringVar(value='—')
        self.mission_label=StringVar(value='')
        self.avatar_image=None
        self.aircraft_hero_image=None
        self.sunset_image=None
        self.header_background=None
        self._market_signature=None
        self._avatar_signature=None
        self._aircraft_code=None
        self._aircraft_image_key=None
        self._country_home=None
        self._last_size=(0,0)

    def text(self,parent,text=None,size=10,color=TEXT,bold=False,bg=None,
             anchor='w',wraplength=0,var=None,**kwargs):
        # Keep all texts in a consistent lightweight Segoe UI scale.
        kw={'textvariable':var} if var is not None else {'text':text or ''}
        return Label(parent,bg=bg or parent.cget('bg'),fg=color,
                     font=(FONT,max(7,round(size*self.theme_scale)),
                           'bold' if bold else 'normal'),anchor=anchor,
                     wraplength=wraplength,**kw,**kwargs)

    @staticmethod
    def card(parent,pad=10,bg=MID_PANEL):
        return Frame(parent,bg=bg,padx=pad,pady=pad,highlightbackground=MID_BORDER,
                     highlightcolor=CYAN,highlightthickness=1,bd=0)

    def button(self,parent,name,callback,accent=False,size=9,pady=7,bg=None,fg=None,width=None,align="center"):
        return GlowButton(parent,name,callback,accent=accent,
                          size=max(7,round(size*self.theme_scale)),pady=pady,bg=bg,fg=fg,
                          align=align, **({"width":width} if width else {}))

    def _photo_into_canvas(self,widget,name,size,*,darken=.15):
        if not widget.winfo_exists():return
        w,h=size
        try:
            img=gradient_image(ASSETS/name,w,h,darken=darken)
        except (OSError,ValueError):img=None
        widget.delete('all')
        if img:
            widget.image_ref=img
            widget.create_image(0,0,image=img,anchor='nw')
            widget.create_rectangle(0,h-2,w, h,fill=blend(CYAN,MID_PANEL,.8),outline='')
        else:
            widget.create_rectangle(0,0,w,h,fill='#102b40',outline='')
            widget.create_text(w/2,h/2,text='Aeronave em uso',fill=MID_MUTED,
                               font=(FONT,10))

    def _draw_avatar(self):
        canvas=self.pilot_avatar
        if not canvas.winfo_exists():return
        w=max(46,canvas.winfo_width());h=max(46,canvas.winfo_height())
        canvas.delete('all')
        p=local_avatar_path(self.app.storage.path.parent)
        if p.exists() and Image:
            try:
                with Image.open(p) as raw:
                    img=ImageOps.fit(ImageOps.exif_transpose(raw).convert('RGB'),(w,h),method=Image.Resampling.LANCZOS)
                mask=Image.new('L',(w,h),0)
                ImageDraw.Draw(mask).rounded_rectangle((0,0,w-1,h-1),radius=8,fill=255)
                img=img.convert('RGBA');img.putalpha(mask)
                avatar=ImageTk.PhotoImage(img)
                canvas.image_ref=avatar
                canvas.create_image(0,0,anchor='nw',image=avatar)
            except (OSError,ValueError):pass
        if not canvas.find_all():
            roundrect(canvas,1,1,w-2,h-2,9,'#17364a','#287597')
            canvas.create_oval(w*.35,h*.2,w*.65,h*.53,fill='#b0c9d7',outline='')
            roundrect(canvas,w*.21,h*.54,w*.79,h*.96,14,'#6c9eb5','')
        roundrect(canvas,1,1,w-2,h-2,8,'',CYAN,1)
        canvas.create_text(w-8,h-9,text='✎',font=(FONT,9,'bold'),fill=CYAN,anchor='se')

    def change_pilot_photo(self):
        path=filedialog.askopenfilename(parent=self.root,title='Foto do piloto — armazenada somente no PC',
             filetypes=[('Fotos','*.png *.jpg *.jpeg *.webp')])
        if not path:return
        if not Image:
            messagebox.showwarning('Imagem','Instale Pillow para utilizar fotos JPG/WEBP.');return
        try:
            with Image.open(path) as im:
                if im.width*im.height>24000000:raise ValueError('Imagem muito grande')
                picture=ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(280,280),method=Image.Resampling.LANCZOS)
            out=local_avatar_path(self.app.storage.path.parent)
            out.parent.mkdir(parents=True,exist_ok=True)
            picture.save(out,format='PNG')
            self._draw_avatar()
        except (OSError,ValueError) as exc:
            messagebox.showwarning('Foto do piloto',str(exc))

    def header(self):
        h=Frame(self.root,bg=MID_BG,height=82)
        h.pack(fill='x');h.pack_propagate(False)
        # A faded aviation-sunset strip blends behind, instead of floating as PNG.
        backdrop=Canvas(h,bg=MID_BG,bd=0,highlightthickness=0)
        backdrop.place(relx=0,rely=0,relwidth=1,relheight=1)
        def paint_header(event=None):
            if not Image:return
            w=max(200,backdrop.winfo_width());height=max(80,backdrop.winfo_height())
            try:
                picture=gradient_image(ASSETS/'header_dusk.png',w,height,soft_corner=0,darken=.48,bottom_fade=False)
                backdrop.delete('all');backdrop.create_image(0,0,image=picture,anchor='nw')
                backdrop.image_ref=picture
                backdrop.create_rectangle(0,0,w,10,fill=MID_BG,outline='')
                backdrop.create_line(0,height-1,w,height-1,fill='#2c647e')
            except (OSError,ValueError):pass
        backdrop.bind('<Configure>',paint_header)
        # Pack the controls directly on the header, leaving the tinted sky
        # image visible between them instead of covering it with an opaque frame.
        frame=h
        # Logo first, title does not compete with XP and cash.
        logo=Frame(frame,bg=MID_BG)
        logo.pack(side='left',padx=(13,8),fill='y')
        title=Frame(logo,bg=MID_BG);title.pack(anchor='w',pady=(11,0))
        self.text(title,'✈',23,CYAN,True,bg=MID_BG).pack(side='left',padx=(0,5))
        self.text(title,'FLIGHTSIM',16,TEXT,True,bg=MID_BG).pack(side='left')
        self.text(title,'CARREIRA',16,CYAN,True,bg=MID_BG).pack(side='left')
        self.text(logo,'SISTEMA DE CARREIRA PARA MSFS 2020',7,MID_MUTED,bg=MID_BG).pack(anchor='w',padx=5)
        controls=Frame(frame,bg=MID_BG)
        controls.pack(side='right',padx=(2,8),fill='y')
        for symbol,action in [('✕',self.app._close),('—',self.root.iconify),('⚙',self.open_settings)]:
            self.button(controls,symbol,action,size=13,pady=8,width=42).pack(side='right',padx=3,pady=17)
        status=self.card(frame,pad=8)
        status.pack(side='right',padx=5,pady=12)
        self.connection_chip=self.text(status,var=self.connection,size=9,color=GREEN,bold=True,bg=MID_PANEL)
        self.connection_chip.pack(anchor='w')
        self.text(status,'SimConnect / modo',7,MID_MUTED,bg=MID_PANEL).pack(anchor='w')
        cash=self.card(frame,pad=7)
        cash.pack(side='right',padx=5,pady=10)
        self.text(cash,'CAIXA DA CARREIRA',7,MID_MUTED,bg=MID_PANEL).pack(anchor='e')
        self.text(cash,var=self.app.balance_var,size=17,color=GOLD,bold=True,bg=MID_PANEL).pack(anchor='e')
        rank=Frame(frame,bg=MID_BG)
        rank.pack(side='right',padx=(2,9),pady=12)
        self.rank_emblem=Canvas(rank,bg=MID_BG,width=40,height=45,highlightthickness=0)
        self.rank_emblem.pack(side='left',padx=(0,7))
        self._paint_rank()
        prog=Frame(rank,bg=MID_BG)
        prog.pack(side='left')
        self.text(prog,var=self.xp_title,size=12,color=CYAN,bold=True,bg=MID_BG).pack(anchor='w')
        self.header_bar=GlowBar(prog,self.app.level_fraction,CYAN,height=13,width=160,bg=MID_BG)
        self.header_bar.pack(fill='x',pady=(3,0))
        self.text(prog,var=self.header_xp_detail,size=7,color=MID_MUTED,bg=MID_BG).pack(anchor='w')
        pilot=Frame(frame,bg=MID_BG)
        pilot.pack(side='right',padx=(1,10),pady=(9,9))
        self.pilot_avatar=Canvas(pilot,width=56,height=56,bg=MID_BG,highlightthickness=0,cursor='hand2')
        self.pilot_avatar.pack(side='left',padx=(0,8))
        self.pilot_avatar.bind('<Configure>',lambda e:self._draw_avatar())
        self.pilot_avatar.bind('<Button-1>',lambda e:self.change_pilot_photo())
        ptxt=Frame(pilot,bg=MID_BG);ptxt.pack(side='left',fill='y')
        flagline=Frame(ptxt,bg=MID_BG);flagline.pack(anchor='w',pady=(8,0))
        self.text(flagline,var=self.pilot_text,size=11,color=TEXT,bold=True,bg=MID_BG).pack(side='left')
        flag=Frame(flagline,bg='#163b4d',padx=4,pady=1,highlightbackground='#2d7890',highlightthickness=1)
        flag.pack(side='left',padx=(6,0))
        self.flag_canvas=Canvas(flag,width=23,height=15,bg='#163b4d',highlightthickness=0,bd=0)
        self.flag_canvas.pack(side='left')
        self.text(flag,var=self.header_flag,size=8,color=GREEN,bold=True,bg='#163b4d').pack(side='left',padx=(3,0))
        self.text(ptxt,var=self.pilot_subtext,size=8,color=MID_MUTED,bg=MID_BG).pack(anchor='w')
        self.text(ptxt,var=self.header_rank,size=8,color=GOLD,bold=True,bg=MID_BG).pack(anchor='w')
        self.pilot_avatar.after_idle(self._draw_avatar)
        self.flag_canvas.after_idle(self._paint_flag)
        self.header= h

    def _paint_flag(self):
        """Base-airport country badge, independent of the pilot's real citizenship."""
        c=self.flag_canvas
        c.delete('all')
        w,h=23,15
        c.create_rectangle(0,0,w,h,fill='#17364b',outline='#3e7183')
        if self.iso_country=='BR':
            c.create_rectangle(1,1,w-2,h-2,fill='#159c50',outline='')
            c.create_polygon(11,2,20,7.5,11,13,2,7.5,fill='#f9d448',outline='')
            c.create_oval(7,4,15,11,fill='#2352a0',outline='')
        elif self.iso_country=='US':
            for y in range(1,h-1,2):c.create_line(1,y,w-2,y,fill='#cb3345',width=1)
            c.create_rectangle(1,1,10,8,fill='#25458b',outline='')
        elif self.iso_country=='PT':
            c.create_rectangle(1,1,9,h-2,fill='#179650',outline='')
            c.create_rectangle(9,1,w-2,h-2,fill='#c42b45',outline='')
            c.create_oval(7,4,13,10,fill='#ebbc3f',outline='')
        else:
            c.create_text(w/2,h/2,text=self.iso_country or '—',
                          fill=MID_MUTED,font=(FONT,8,'bold'))


    def _paint_rank(self):
        c=self.rank_emblem;c.delete('all')
        c.create_polygon(20,3,35,11,31,31,20,42,9,31,5,11,fill='#382f17',outline=GOLD,width=1.5)
        c.create_text(20,21,text='★',fill=GOLD,font=('Segoe UI Symbol',16,'bold'))
        for i in range(min(3,max(1,self.rank_level//4+1))):
            c.create_oval(11+i*7,34,14+i*7,37,fill=GOLD,outline='')
        c.create_line(4,18,12,18,fill=GOLD,width=2)
        c.create_line(28,18,36,18,fill=GOLD,width=2)

    def sidebar(self,parent):
        side=Frame(parent,bg='#071827',width=188)
        side.grid(row=0,column=0,sticky='nsew',padx=(2,6),pady=4)
        side.grid_propagate(False)
        side.grid_rowconfigure(0,weight=1)
        nav=Frame(side,bg='#071827');nav.grid(row=0,column=0,sticky='nsew')
        nav.grid_columnconfigure(0,weight=1)
        self.text(nav,'OPERAÇÕES',8,GOLD,True,bg='#071827').pack(anchor='w',padx=10,pady=(9,6))
        items=[('⌂','Dashboard',lambda:self.activate('Dashboard')),
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
        for ico,name,action in items:
            b=self.button(nav,f'{ico}   {name}',action,size=9,pady=6,
                         bg=('#105e74' if name=='Dashboard' else '#0b2335'),align='left')
            b.pack(fill='x',padx=5,pady=(0,2))
            self.nav_buttons[name]=b
        art=Canvas(side,height=155,bg='#071827',highlightthickness=0)
        art.grid(row=1,column=0,sticky='sew',padx=4,pady=(2,4))
        def on_art(event):
            w=max(60,event.width);h=max(50,event.height)
            self._photo_into_canvas(art,'sidebar_sunset.png',(w,h),darken=.23)
        art.bind('<Configure>',on_art)
        self.sidebar_frame=side

    def activate(self,name):
        self.selected_nav=name
        for label,b in self.nav_buttons.items():
            b.configure(bg='#105e74' if label==name else '#0b2335')

    def build(self):
        self.root.title('FlightSimCarreira • Midnight Ops | v0.6.3 Alpha.1')
        sw,sh=self.root.winfo_screenwidth(),self.root.winfo_screenheight()
        width=min(sw, max(1110,int(sw*.96)))
        height=min(sh-42,max(630,int(sh*.94)))
        self.theme_scale=min(1.18,max(.84,width/1660))
        self.root.geometry(f'{width}x{height}+{max(0,(sw-width)//2)}+{max(0,(sh-height-42)//2)}')
        self.root.minsize(min(1180,sw),min(670,sh-42))
        self.root.configure(bg=MID_BG)
        self.header()
        body=Frame(self.root,bg=MID_BG)
        body.pack(fill='both',expand=True,padx=3,pady=(5,3))
        body.grid_rowconfigure(0,weight=1)
        body.grid_columnconfigure(0,weight=0,minsize=176)
        body.grid_columnconfigure(1,weight=1)
        self.sidebar(body)
        layout=Frame(body,bg=MID_BG)
        layout.grid(row=0,column=1,sticky='nsew')
        layout.grid_rowconfigure(0,weight=1)
        layout.grid_columnconfigure(0,weight=2,minsize=220)
        layout.grid_columnconfigure(1,weight=5,minsize=410)
        layout.grid_columnconfigure(2,weight=2,minsize=235)
        self.left_column(layout)
        self.center_column(layout)
        self.right_column(layout)
        self.app.mission_select=ttk.Combobox(self.root,state='readonly',values=[])
        self.app.history_text=Text(self.root,bd=0,height=1)
        self.app._refresh_history()
        self.layout=layout
        self.refresh(force_market=True)
        self.root.bind('<Configure>',self._on_window_resize,add='+')

    def _on_window_resize(self,event):
        if event.widget is not self.root:return
        size=(event.width,event.height)
        if size==self._last_size:return
        self._last_size=size
        self.root.after_idle(self._resize_content)

    def _resize_content(self):
        if not self.root.winfo_exists():return
        # No root scrollbar: distribute the available height across all sections.
        h=max(460,self.layout.winfo_height())
        # Map flexes most; contract and telemetry remain compact.
        compact=h<680
        self.middle.grid_rowconfigure(0,minsize=(68 if compact else 78),weight=0)
        self.middle.grid_rowconfigure(1,minsize=(184 if compact else 200),weight=8)
        self.middle.grid_rowconfigure(2,minsize=(78 if compact else 92),weight=0)
        self.middle.grid_rowconfigure(3,minsize=(58 if compact else 68),weight=0)
        self.middle.grid_rowconfigure(4,minsize=(118 if compact else 145),weight=4)
        if hasattr(self,'right_grid'):
            self.right_grid.grid_rowconfigure(0,weight=(5 if h>=690 else 8),minsize=(365 if h>=690 else 370))
            self.right_grid.grid_rowconfigure(1,weight=2,minsize=93)
            self.right_grid.grid_rowconfigure(2,weight=(2 if h>=690 else 1),minsize=(110 if h>=690 else 72))
            desired_image=120 if h<690 else min(230,120+int((h-690)*.46))
            if int(self.aircraft_canvas.cget('height'))!=desired_image:
                self.aircraft_canvas.configure(height=desired_image)
        if hasattr(self,'realmode_widget'):
            if h<625:
                self.realmode_widget.pack_forget()
            elif not self.realmode_widget.winfo_manager():
                self.realmode_widget.pack(before=self.realism_options_frame,anchor='w',pady=(2,1))
        if hasattr(self,'extra_fleet_button'):
            if h<630:
                self.extra_fleet_button.pack_forget()
            elif not self.extra_fleet_button.winfo_manager():
                self.extra_fleet_button.pack(fill='x',pady=(5,0))
        self.redraw_map()

    def _section_header(self,parent,text,color=CYAN):
        self.text(parent,text,10,color,True,bg=MID_PANEL).pack(anchor='w',pady=(0,4))

    def left_column(self,main):
        col=Frame(main,bg=MID_BG)
        col.grid(row=0,column=0,sticky='nsew',padx=(0,5),pady=3)
        col.grid_columnconfigure(0,weight=1)
        col.grid_rowconfigure(0,weight=7,minsize=305)
        col.grid_rowconfigure(1,weight=3,minsize=170)
        market=self.card(col,pad=7)
        market.grid(row=0,column=0,sticky='nsew',pady=(0,5));market.grid_propagate(False)
        market.grid_columnconfigure(0,weight=1)
        market.grid_rowconfigure(2,weight=1)
        self.text(market,'MERCADO REGIONAL',10,TEXT,True,bg=MID_PANEL).grid(row=0,column=0,sticky='w')
        self.text(market,var=self.market_airport,size=8,color=MID_MUTED,bg=MID_PANEL).grid(row=1,column=0,sticky='w',pady=(0,5))
        self.market_rows=Frame(market,bg=MID_PANEL)
        self.market_rows.grid(row=2,column=0,sticky='nsew')
        self.button(market,'⌕  Ver todas as missões',self.app._market_window,size=9,pady=5).grid(row=3,column=0,sticky='ew',pady=(4,0))
        summary=self.card(col,pad=9)
        summary.grid(row=1,column=0,sticky='nsew');summary.grid_propagate(False)
        summary.grid_columnconfigure(0,weight=1)
        self.text(summary,'▥  RESUMO DA CARREIRA',10,TEXT,True,bg=MID_PANEL).pack(anchor='w',pady=(0,7))
        data=[('✈  Voos realizados',self.career_flights),('◷  Horas de voo',self.career_hours),
              ('★  Habilitações',self.career_qualifications),('◉  Caixa atual',self.app.balance_var)]
        for title,var in data:
            line=Frame(summary,bg=MID_PANEL);line.pack(fill='x',pady=2)
            self.text(line,title,8,MID_MUTED,bg=MID_PANEL).pack(side='left')
            self.text(line,var=var,size=9,color=GOLD if 'Caixa' in title else TEXT,bold=True,bg=MID_PANEL).pack(side='right')
        line=Frame(summary,bg=MID_PANEL);line.pack(fill='x',pady=(5,0))
        self.text(line,'Reputação',8,MID_MUTED,bg=MID_PANEL).pack(side='left')
        self.text(line,var=self.career_reputation,size=9,color=GREEN,bg=MID_PANEL).pack(side='right')
        self.reputation_bar=GlowBar(summary,0,GREEN,height=10,bg=MID_PANEL)
        self.reputation_bar.pack(fill='x',pady=(3,0))
        self.text(summary,'PROGRESSO DE NÍVEL',7,MID_MUTED,True,bg=MID_PANEL).pack(anchor='w',pady=(4,0))
        self.left_xp_bar=GlowBar(summary,self.app.level_fraction,CYAN,height=10,bg=MID_PANEL)
        self.left_xp_bar.pack(fill='x',pady=(6,0))

    def _metric(self,parent,key,title,unit,idx):
        f=Frame(parent,bg=MID_CARD,highlightbackground=MID_BORDER,highlightthickness=1)
        f.grid(row=0,column=idx,sticky='nsew',padx=(0 if idx==0 else 3,0))
        parent.grid_columnconfigure(idx,weight=1,uniform='metric')
        self.text(f,title,7,MID_MUTED,True,bg=MID_CARD,anchor='center').pack(fill='x',pady=(5,0))
        v=self.phase_badge if key=='phase' else self.app.flight_vars[key]
        self.text(f,var=v,size=14,color=GREEN if key=='phase' else TEXT,bold=True,bg=MID_CARD,anchor='center').pack(fill='x',pady=(3,0))
        self.text(f,unit or ' ',7,MID_MUTED,bg=MID_CARD,anchor='center').pack(fill='x')

    def center_column(self,main):
        col=Frame(main,bg=MID_BG)
        col.grid(row=0,column=1,sticky='nsew',padx=2,pady=3)
        col.grid_columnconfigure(0,weight=1)
        self.middle=col
        for r,weight,minsz in ((0,0,78),(1,7,178),(2,0,95),(3,0,67),(4,5,140)):
            col.grid_rowconfigure(r,weight=weight,minsize=minsz)
        contract=self.card(col,pad=6)
        contract.configure(height=72)
        contract.grid(row=0,column=0,sticky='nsew',pady=(0,4));contract.grid_propagate(False)
        self.text(contract,'▣  CONTRATO ATIVO',10,CYAN,True,bg=MID_PANEL).pack(anchor='w')
        mainline=Frame(contract,bg=MID_PANEL);mainline.pack(fill='x',pady=(1,0))
        brief=Frame(mainline,bg=MID_PANEL);brief.pack(side='left',fill='x',expand=True)
        self.text(brief,var=self.mission_route,size=14,color=TEXT,bold=True,bg=MID_PANEL).pack(anchor='w')
        self.text(brief,var=self.mission_title,size=9,color=MID_MUTED,bg=MID_PANEL).pack(anchor='w')
        amount=Frame(mainline,bg=MID_PANEL);amount.pack(side='right')
        self.text(amount,'PAGAMENTO BRUTO',7,MID_MUTED,bg=MID_PANEL).pack(anchor='e')
        self.text(amount,var=self.mission_pay,size=12,color=GOLD,bold=True,bg=MID_PANEL).pack(anchor='e')
        self.text(amount,var=self.mission_bonus,size=8,color=GREEN,bg=MID_PANEL).pack(anchor='e')
        box=self.card(col,pad=6)
        box.grid(row=1,column=0,sticky='nsew',pady=3);box.grid_propagate(False)
        box.grid_rowconfigure(1,weight=1);box.grid_columnconfigure(0,weight=1)
        head=Frame(box,bg=MID_PANEL);head.grid(row=0,column=0,sticky='ew')
        self.text(head,'MAPA E TRAJETO',10,TEXT,True,bg=MID_PANEL).pack(side='left')
        self.text(head,'ROTA ESQUEMÁTICA • DADOS REAIS',7,MID_MUTED,bg=MID_PANEL).pack(side='right')
        self.map_canvas=Canvas(box,bg='#081b2a',bd=0,highlightthickness=0)
        self.map_canvas.grid(row=1,column=0,sticky='nsew',pady=(4,1))
        self.map_canvas.bind('<Configure>',lambda e:self.redraw_map())
        tabs=Frame(box,bg=MID_PANEL);tabs.grid(row=2,column=0,sticky='ew')
        for i,(name,fn) in enumerate([('Mapa e Rota',self.app._prepare_active_plan),
                 ('METAR / Clima',self.open_weather),('Pistas e Luzes',self.app._planning_window),
                 ('Peso / Balanceamento',self.app._planning_window),('Plano VFR',self.app._prepare_active_plan)]):
            self.button(tabs,name,fn,accent=i==0,size=8,pady=3).pack(side='left',fill='x',expand=True,padx=(0 if i==0 else 3,0))
        tele=self.card(col,pad=5)
        tele.configure(height=78)
        tele.grid(row=2,column=0,sticky='nsew',pady=3);tele.grid_propagate(False)
        self.text(tele,'◉  TELEMETRIA AO VIVO',9,CYAN,True,bg=MID_PANEL).pack(anchor='w',pady=(0,1))
        metrics=Frame(tele,bg=MID_PANEL);metrics.pack(fill='both',expand=True)
        for i,(key,title,unit) in enumerate([('ias','IAS','kt'),('gs','SOLO','kt'),
                        ('alt','ALTITUDE','ft'),('agl','AGL','ft'),('vs','VERTICAL','ft/min'),('phase','FASE','')]):
            self._metric(metrics,key,title,unit,i)
        metar=Frame(col,bg=MID_BG);metar.grid(row=3,column=0,sticky='nsew',pady=3)
        for j,(label,var) in enumerate([('METAR ORIGEM',self.wind_origin),('METAR DESTINO',self.wind_dest)]):
            card=self.card(metar,pad=8)
            card.pack(side='left',fill='both',expand=True,padx=(0,3) if j==0 else (3,0))
            self.text(card,label,8,CYAN,True,bg=MID_PANEL).pack(anchor='w')
            self.text(card,var=var,size=8,color=MID_MUTED,bg=MID_PANEL,wraplength=290).pack(anchor='w',pady=(4,0))
        bottom=Frame(col,bg=MID_BG);bottom.grid(row=4,column=0,sticky='nsew',pady=(3,0))
        bottom.grid_rowconfigure(0,weight=1);bottom.grid_columnconfigure(0,weight=5,minsize=150);bottom.grid_columnconfigure(1,weight=4,minsize=165)
        log=self.card(bottom,pad=7)
        log.grid(row=0,column=0,sticky='nsew',padx=(0,3));log.grid_propagate(False)
        self.text(log,'▤  REGISTRO DO VOO',9,TEXT,True,bg=MID_PANEL).pack(anchor='w')
        self.app.log_text=Text(log,bg='#071827',fg='#bcd8e7',height=4,
               font=('Consolas',8),width=1,bd=0,relief='flat',wrap='word',padx=6,pady=5,
               insertbackground=CYAN,state='disabled')
        self.app.log_text.pack(fill='both',expand=True,pady=(3,0))
        bonus=self.card(bottom,pad=5)
        bonus.grid(row=0,column=1,sticky='nsew',padx=(3,0));bonus.grid_propagate(False)
        self.text(bonus,'★  BÔNUS DE REALISMO',9,GOLD,True,bg=MID_PANEL).pack(anchor='w')
        self.realmode_widget=self.text(bonus,var=self.realmode_label,size=7,color=GREEN,bg=MID_PANEL,
                  wraplength=270)
        self.realmode_widget.pack(anchor='w',pady=(2,1))
        options=Frame(bonus,bg=MID_PANEL);options.pack(fill='x')
        self.realism_options_frame=options
        for i,(label,key) in enumerate([('Clima ao vivo','real_weather_declared'),
            ('Horário real','real_time_declared'),('Assistências realistas','assists_realistic_declared'),
            ('Pistas e iluminação','runway_checked'),('Rota revisada','route_checked'),
            ('Reserva conferida','fuel_checked'),('Peso verificado','payload_checked')]):
            colid=i%2;rowid=i//2
            var=StringVar(value='□');self.realism_items[key]=var
            sub=Frame(options,bg=MID_PANEL);sub.grid(row=rowid,column=colid,sticky='w',padx=(0,5))
            self.text(sub,var=var,size=9,color=GREEN,bg=MID_PANEL).pack(side='left')
            self.text(sub,' '+label,size=7,color=TEXT,bg=MID_PANEL).pack(side='left')
        # Existing planner is the only source of truth for the checkbox values.
        self.bonus_edit_btn=self.button(bonus,'Editar pré-voo',self.app._planning_window,size=8,pady=1)
        self.bonus_edit_btn.pack(fill='x',pady=(2,0))

    def right_column(self,main):
        col=Frame(main,bg=MID_BG)
        col.grid(row=0,column=2,sticky='nsew',padx=(5,0),pady=3)
        col.grid_columnconfigure(0,weight=1)
        self.right_grid=col
        col.grid_rowconfigure(0,weight=8,minsize=370)
        col.grid_rowconfigure(1,weight=2,minsize=93)
        col.grid_rowconfigure(2,weight=1,minsize=72)
        aircraft=self.card(col,pad=9)
        aircraft.grid(row=0,column=0,sticky='nsew',pady=(0,5));aircraft.grid_propagate(False)
        self.text(aircraft,'AERONAVE EM USO',10,TEXT,True,bg=MID_PANEL).pack(anchor='w',pady=(0,4))
        self.aircraft_canvas=Canvas(aircraft,bg=MID_PANEL,
            height=(120 if self.root.winfo_screenheight()<800 else
                    175 if self.root.winfo_screenheight()<1050 else 215),
            width=195,bd=0,highlightthickness=0)
        self.aircraft_canvas.pack(fill='x')
        self.aircraft_canvas.bind('<Configure>',self._redraw_aircraft)
        # Base refresh compatibility (PhotoCanvas is a canvas, text configurable through wrapper).
        self.aircraft_photo=Label(aircraft,bg=MID_PANEL,text='',fg=MID_MUTED)
        self.text(aircraft,var=self.aircraft_title,size=11,color=TEXT,bold=True,bg=MID_PANEL,wraplength=230).pack(anchor='w',pady=(7,0))
        self.text(aircraft,var=self.aircraft_ref,size=8,color=MID_MUTED,bg=MID_PANEL).pack(anchor='w')
        for field,var in [('Localização',self.airport),('Estado',self.condition),('Combustível',self.fuel_amount)]:
            row=Frame(aircraft,bg=MID_PANEL);row.pack(fill='x',pady=(7,0))
            self.text(row,field,8,MID_MUTED,bg=MID_PANEL).pack(side='left')
            self.text(row,var=var,size=9,color=TEXT,bold=True,bg=MID_PANEL).pack(side='right')
        self.condition_bar=GlowBar(aircraft,0,GREEN,height=9,bg=MID_PANEL)
        self.condition_bar.pack(fill='x',pady=(4,2))
        self.fuel_bar=GlowBar(aircraft,0,CYAN,height=10,bg=MID_PANEL)
        self.fuel_bar.pack(fill='x',pady=(2,5))
        self.fuel_fraction=0.0
        self.fuel_btn=self.button(aircraft,'CONTROLE DE COMBUSTÍVEL: ATIVO',self.toggle_fuel,
                                  bg='#104539',fg=GREEN,pady=6,size=8)
        self.fuel_btn.pack(fill='x',pady=(1,5))
        actions=Frame(aircraft,bg=MID_PANEL);actions.pack(fill='x')
        self.refuel_button=self.button(actions,'Abastecer',self.refuel_selected,accent=True,pady=6)
        self.refuel_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.service_button=self.button(actions,'Revisar',self.service_selected,pady=6)
        self.service_button.pack(side='left',fill='x',expand=True,padx=(3,0))
        flight=self.card(col,pad=9)
        flight.grid(row=1,column=0,sticky='nsew',pady=5);flight.grid_propagate(False)
        self.button(flight,'✈  Preparar Voo / Despacho',self.app._planning_window,
                    accent=True,size=10,pady=8).pack(fill='x',pady=(0,5))
        self.button(flight,'⇩  Carregar plano VFR no MSFS',self.app._prepare_active_plan,size=9,pady=7).pack(fill='x')
        extra=self.card(col,pad=8)
        extra.grid(row=2,column=0,sticky='nsew',pady=(5,0));extra.grid_propagate(False)
        self.text(extra,'RESUMO DO VOO',9,GOLD,True,bg=MID_PANEL).pack(anchor='w')
        self.text(extra,var=self.flight_summary,size=8,color=MID_MUTED,bg=MID_PANEL,wraplength=235).pack(anchor='w',pady=(4,0))
        self.extra_fleet_button=self.button(extra,'Ver frota completa',self.app._fleet_window,size=8,pady=4)
        self.extra_fleet_button.pack(fill='x',pady=(5,0))

    def _redraw_aircraft(self,event=None):
        c=self.aircraft_canvas
        if not c.winfo_exists():return
        w=max(70,c.winfo_width());h=max(70,c.winfo_height())
        key=(w,h,self._aircraft_code)
        if key==self._aircraft_image_key:return
        self._aircraft_image_key=key
        name='cessna_152_concept.png' if self._aircraft_code in (None,'c152') else None
        if name:self._photo_into_canvas(c,name,(w,h),darken=.13)
        else:
            c.delete('all');roundrect(c,0,0,w,h,8,'#102d41','#24536c')
            c.create_text(w/2,h/2,text='Imagem do modelo indisponível',fill=MID_MUTED,font=(FONT,9))
        c.create_text(w-10,h-10,text='ARTE ILUSTRATIVA',fill='#d7f0ff',font=(FONT,7),anchor='se')

    def _draw_fraction(self,canvas,fraction,color=CYAN):
        if isinstance(canvas,GlowBar):
            canvas.fill_color=color;canvas.set_fraction(fraction)
        else:super()._draw_fraction(canvas,fraction,color)

    def update_market(self,force=False):
        """Present cached local offers without loading world-wide contract cards."""
        super().update_market(force=force)
        signature=tuple((m.id,m.reward) for m in self.market_offers[:5])
        if signature==self._market_signature and not force:return
        self._market_signature=signature
        for w in self.market_rows.winfo_children():w.destroy()
        for i,offer in enumerate(self.market_offers[:5]):
            line=Frame(self.market_rows,bg=('#123c53' if i==0 else MID_CARD),
                       highlightbackground=(GOLD if i==0 else MID_BORDER),
                       highlightthickness=1,cursor='hand2')
            line.pack(fill='both',expand=True,pady=(0,4))
            line.pack_propagate(False)
            bg=line.cget('bg')
            cat=TYPE_BY_CODE.get(offer.category)
            title=(cat.title if cat else offer.title)
            if offer.freelance:title+=' • Freelance'
            details=Frame(line,bg=bg)
            details.pack(side='left',fill='both',expand=True,padx=(6,0),pady=4)
            ico={'cargo':'▣','tourism':'✈','passenger':'♟','airtaxi':'✈','medical':'✚',
                 'executive':'★','rescue':'⚑'}.get(offer.category,'✈')
            self.text(details,f'{ico}  {title}',8,TEXT,True,bg=bg,
                      wraplength=140).pack(anchor='w')
            self.text(details,f'{offer.origin} → {offer.destination}',8,MID_MUTED,bg=bg).pack(anchor='w')
            price=Frame(line,bg=bg)
            price.pack(side='right',fill='y',padx=(2,6),pady=4)
            self.text(price,brl(offer.reward),9,GOLD,True,bg=bg).pack(anchor='e')
            try:
                d=distance_nm(offer.origin_lat,offer.origin_lon,
                              offer.destination_lat,offer.destination_lon)
                minutes=estimated_minutes(d)
                self.text(price,f'~{minutes} min',7,MID_MUTED,bg=bg).pack(anchor='e')
            except (ValueError,TypeError,AttributeError):pass
            def open_offer(event=None):self.app._market_window()
            for widget in [line,details,price,*details.winfo_children(),*price.winfo_children()]:
                widget.bind('<Button-1>',open_offer)
        if not self.market_offers:
            self.text(self.market_rows,'Nenhuma proposta disponível aqui.\nAbra o mercado para procurar.',
                      9,MID_MUTED,bg=MID_PANEL,wraplength=180).pack(anchor='w',pady=12)

    def refresh(self,force_market=False):
        super().refresh(force_market=force_market)
        p=self.app.storage.get_pilot()
        stats=self.app.storage.pilot_stats() if p else {}
        prog=level_progress(int(stats.get('xp',0)))
        self.header_bar.set_fraction(prog['fraction'])
        self.header_xp_detail.set('XP até o próximo nível: '+f"{round(prog['fraction']*100)}%")
        self.left_xp_bar.set_fraction(prog['fraction'])
        quals=stats.get('qualifications',set())
        rank,title=level_to_rank(prog['level'],quals)
        self.header_rank.set(title)
        self.rank_code=rank
        self.rank_level=prog['level']
        self._paint_rank()
        home=p.get('home_icao','') if p else ''
        if home!=self._country_home:
            self._country_home=home
            self.iso_country=nationality_from_base(home)
            self.header_flag.set(self.iso_country or '—')
            self._paint_flag()
        # Reputation economy is not implemented yet. If a future build stores
        # a legitimate reputation score, render it without manufacturing data.
        raw_rep=self.app.storage.get_setting('reputation_score')
        try:
            if raw_rep is None:raise ValueError('unset')
            rep=min(100.,max(0.,float(raw_rep)))
        except (ValueError,TypeError):
            self.career_reputation.set('—')
            self.reputation_bar.set_fraction(0)
        else:
            self.career_reputation.set(f'{rep:.0f}%')
            self.reputation_bar.fill_color=GREEN if rep>=65 else GOLD if rep>=35 else RED
            self.reputation_bar.set_fraction(rep/100)

        selected=self.app.storage.fleet_manager().selected()
        new_aircraft_code=selected['code'] if selected else None
        if self._aircraft_code != new_aircraft_code:
            self._aircraft_code=new_aircraft_code
            self._aircraft_image_key=None
        if selected:
            self.condition_bar.set_fraction(max(0.,min(1.,selected['condition']/100)))
        else:self.condition_bar.set_fraction(0)
        self._draw_fraction(self.fuel_bar,self.fuel_fraction,CYAN)
        self._redraw_aircraft()

    def open_settings(self):
        """Existing settings/controls, plus an explicit discoverable avatar chooser."""
        win=Toplevel(self.root)
        win.title('FlightSimCarreira • Configurações Midnight Ops')
        win.geometry('550x480')
        win.configure(bg=MID_BG)
        panel=self.card(win,pad=18)
        panel.pack(fill='both',expand=True,padx=12,pady=12)
        self.text(panel,'CONFIGURAÇÕES',16,CYAN,True,bg=MID_PANEL).pack(anchor='w')
        self.text(panel,'Personalização da interface e ferramentas existentes.',9,
                  MID_MUTED,bg=MID_PANEL).pack(anchor='w',pady=(4,12))
        actions=[('Selecionar foto do piloto (somente neste PC)',self.change_pilot_photo),
                ('Conectar ao MSFS',self.app._connect),
                ('Desconectar do simulador',self.app._stop),
                ('Demonstração sem MSFS',self.app._demo_start),
                ('Aceitar contrato de teste',lambda:self.app._accept_specific(MISSIONS[0])),
                ('Avançar demonstração',self.app._demo_next),
                ('Finanças e controle de combustível',self.app._finance_window),
                ('Salvar log de diagnóstico',self.app._save_log),
                ('Painel web local',self.app._open_local_panel)]
        for label,callback in actions:
            self.button(panel,label,callback,size=9,pady=5).pack(fill='x',pady=2)


    def redraw_map(self):
        c=self.map_canvas
        if not c or not c.winfo_exists():return
        c.delete('all')
        w=max(80,c.winfo_width());h=max(60,c.winfo_height())
        c.create_rectangle(0,0,w,h,fill='#081b2a',outline='')
        # Calm topographic-like ornamental background; not falsely labelled satellite.
        for x in range(0,w,38):c.create_line(x,0,x,h,fill='#103246')
        for y in range(0,h,35):c.create_line(0,y,w,y,fill='#103246')
        from math import sin,isfinite
        for i in range(4):
            nodes=[(j, max(0, min(h, round((.25+i*.16)*h + 10*sin((j+i*40)/63))))) for j in range(0,w+8,8)]
            c.create_line(nodes,fill='#123d50',width=1,smooth=True)
        m=self.app.career.mission
        if not m:
            c.create_text(w/2,h/2-9,text='AGUARDANDO MISSÃO',fill='#adcad9',font=(FONT,13,'bold'))
            c.create_text(w/2,h/2+16,text='Escolha uma proposta para visualizar a rota',fill=MID_MUTED,font=(FONT,9))
            return
        a,b=safe_coords(m)
        if not a or not b or not all(isfinite(x) for x in (*a,*b)):
            c.create_text(w/2,h/2,text='COORDENADAS NÃO DISPONÍVEIS',fill=MID_MUTED,font=(FONT,10))
            return
        latmin=min(a[0],b[0])-.025;latmax=max(a[0],b[0])+.025
        lonmin=min(a[1],b[1])-.025;lonmax=max(a[1],b[1])+.025
        def project(lat,lon):
            return (26+(lon-lonmin)/(lonmax-lonmin)*(w-52),
                    h-28-(lat-latmin)/(latmax-latmin)*(h-56))
        ax,ay=project(*a);bx,by=project(*b)
        c.create_line(ax,ay,bx,by,fill='#0a546e',width=8)
        c.create_line(ax,ay,bx,by,fill=CYAN,width=3)
        for px,py,label in [(ax,ay,m.origin),(bx,by,m.destination)]:
            c.create_oval(px-9,py-9,px+9,py+9,fill='#0c3d52',outline='#9ef0ff',width=2)
            c.create_oval(px-3,py-3,px+3,py+3,fill=CYAN,outline='')
            c.create_text(px,py-18 if py>31 else py+20,text=label,fill=TEXT,font=(FONT,10,'bold'))
        s=self.app.last_sample if self.app.connected else None
        if s and latmin<=s.latitude<=latmax and lonmin<=s.longitude<=lonmax:
            px,py=project(s.latitude,s.longitude)
            c.create_oval(px-10,py-10,px+10,py+10,outline=GOLD,width=2)
            c.create_text(px,py,text='✈',fill=TEXT,font=(FONT,16,'bold'))
        c.create_text(w-7,h-10,text='MAPA ESQUEMÁTICO',anchor='e',fill='#88b0c1',font=(FONT,7))
