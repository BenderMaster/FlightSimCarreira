"""Midnight Ops visual primitives, deliberately independent from career logic.

Canvas components are keyboard-accessible and use Tk itself (no theme package).
"""
from __future__ import annotations
import tkinter as tk
from math import sin, pi

BG = '#061321'
PANEL = '#0a1d2d'
BORDER = '#1f526e'
CYAN = '#35d6ff'
AMBER = '#f4bd49'
GREEN = '#4de2a1'
TEXT = '#eaf7ff'
MUTED = '#a4c0d1'


def blend(a: str, b: str, t: float) -> str:
    t=max(0.,min(1.,t))
    return '#'+''.join(f'{round(int(a[i:i+2],16)*(1-t)+int(b[i:i+2],16)*t):02x}' for i in (1,3,5))


def rounded_points(x0, y0, x1, y1, r):
    r=max(0,min(r,(x1-x0)/2,(y1-y0)/2))
    return [x0+r,y0,x1-r,y0,x1,y0,x1,y0+r,x1,y1-r,x1,y1,
            x1-r,y1,x0+r,y1,x0,y1,x0,y1-r,x0,y0+r,x0,y0]


def roundrect(canvas, x0,y0,x1,y1,r, fill, outline='', width=1, **kwargs):
    return canvas.create_polygon(rounded_points(x0,y0,x1,y1,r),smooth=True,
         splinesteps=20,fill=fill,outline=outline,width=width,**kwargs)


class GlowBar(tk.Canvas):
    """Responsive gradient meter. It has a real independent fraction, never XP text."""
    def __init__(self,parent,fraction=0.,color=CYAN,height=13,**kw):
        self.track_bg=kw.pop('bg',PANEL)
        kw.setdefault('width',80)
        super().__init__(parent,background=self.track_bg,highlightthickness=0,bd=0,
                         height=height,**kw)
        self.fraction=max(0.,min(1.,fraction))
        self.fill_color=color
        self.bind('<Configure>',lambda e:self.redraw())

    def set_fraction(self,f):
        self.fraction=max(0.,min(1.,float(f)))
        self.redraw()

    def redraw(self):
        if not self.winfo_exists():return
        w=max(6,self.winfo_width());h=max(5,self.winfo_height());self.delete('all')
        roundrect(self,0,1,w,h-1,min(7,h/2),'#102e41','#205273',1)
        length=(w-2)*self.fraction
        if length<2:return
        # cyan/green luminous gradient reminiscent of the approved reference
        c=self.fill_color
        for i in range(max(1,int(length))):
            t=i/max(1,length)
            col=blend(blend(c,'#ffffff',.20),c,.35+.45*t)
            self.create_line(1+i,3,1+i,h-3,fill=col)
        self.create_line(2,2,min(w-2,length),2,fill=blend(c,'#ffffff',.55))
        self.create_line(2,h-2,min(w-2,length),h-2,fill=blend(c,'#000000',.35))
        if length>12:
            self.create_oval(max(0,length-9),2,min(w,length+2),h-2,
                             outline=blend(c,'#ffffff',.3),width=1)


class GlowButton(tk.Canvas):
    """Rounded high contrast button, hover and keyboard activation, Tk compatible."""
    def __init__(self,parent,text,command,accent=False,size=9,pady=8,bg=None,fg=None,
                 icon=None,align="center",**kwargs):
        self.label=text;self.callback=command;self.accent=accent
        self.base=bg or (CYAN if accent else '#122c43')
        self.fg=fg or ('#041624' if accent else TEXT)
        self.size=size;self.hover=False;self.align=align
        self.h=max(27,round(20+pady*2));self.disabled=False
        super().__init__(parent,background=parent.cget('bg'),highlightthickness=0,
                         bd=0,height=self.h,width=kwargs.pop('width',120),takefocus=1,**kwargs)
        self.bind('<Configure>',lambda e:self.redraw())
        self.bind('<Enter>',self._enter)
        self.bind('<Leave>',self._leave)
        self.bind('<Button-1>',lambda e:self.invoke())
        self.bind('<Return>',lambda e:self.invoke())
        self.bind('<space>',lambda e:self.invoke())
        self.bind('<FocusIn>',lambda e:self.redraw())
        self.bind('<FocusOut>',lambda e:self.redraw())

    def _enter(self,e):
        self.hover=True
        self.configure(cursor='hand2' if not self.disabled else 'arrow')
        self.redraw()

    def _leave(self,e):
        self.hover=False;self.redraw()

    def invoke(self):
        if not self.disabled and callable(self.callback):self.callback()

    def configure(self,cnf=None,**kw):
        if cnf:kw.update(cnf)
        if 'text' in kw:self.label=kw.pop('text')
        if 'bg' in kw:self.base=kw.pop('bg')
        if 'fg' in kw:self.fg=kw.pop('fg')
        if 'state' in kw:self.disabled=kw.pop('state')=='disabled'
        result=super().configure(**kw) if kw else None
        if hasattr(self,'label'):self.redraw()
        return result
    config=configure

    def redraw(self):
        if not self.winfo_exists():return
        w=max(25,self.winfo_width());h=max(20,self.winfo_height());self.delete('all')
        base=blend(self.base,'#ffffff',.07 if self.hover else 0.)
        if self.disabled:base='#132435'
        border=blend(base,'#ffffff',.22 if self.accent else .17)
        if self.hover:border=blend(border,CYAN,.42)
        roundrect(self,2,3,w-2,h-2,9,blend(BG,'#000000',.3),'',0)
        roundrect(self,1,1,w-2,h-4,8,base,border,1)
        self.create_line(13,3,w-14,3,fill=blend(base,'#ffffff',.26 if self.accent else .13),width=1)
        textcolor=('#7d91a4' if self.disabled else self.fg)
        if self.winfo_width()<85:
            label=self.label.split('  ')[-1][:12]
        else:label=self.label
        self.create_text(12 if self.align=='left' else w/2,(h-3)/2,text=label,fill=textcolor,
                         font=('Segoe UI',self.size,'bold'),anchor=('w' if self.align=='left' else 'center'))
        if self.focus_get()==self:roundrect(self,3,3,w-4,h-6,7,'',CYAN,1)
