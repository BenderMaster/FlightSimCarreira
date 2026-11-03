"""Run per Xvfb/Windows resolution; verifies that essential controls remain visible."""
from pathlib import Path
from unittest.mock import patch
from tkinter import Scrollbar
import tempfile
from aerocarreira.app import Application

with tempfile.TemporaryDirectory() as p:
  with patch('aerocarreira.app.state_dir',return_value=Path(p)):
    app=Application()
    app.storage.create_pilot('Piloto Teste','BM2564','SBRF')
    app._refresh_pilot_summary()
    app.ui.refresh(force_market=True)
    app.root.update()
    app.root.after(300,app.root.quit);app.root.mainloop()
    root=app.root
    assert app.ui.scroll_canvas is None, 'Root scroll canvas returned'
    bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_width(),root.winfo_height())
    for attr in ('bonus_edit_btn','refuel_button','service_button','fuel_btn','map_canvas'):
      widget=getattr(app.ui,attr)
      assert widget.winfo_viewable(),f'{attr}: widget not visible'
      x,y=widget.winfo_rootx()-bbox[0],widget.winfo_rooty()-bbox[1]
      w,h=widget.winfo_width(),widget.winfo_height()
      assert x>=0 and y>=0 and x+w<=bbox[2]+3 and y+h<=bbox[3]+3,(attr,(x,y,w,h),bbox)
    print('FIT_OK',root.winfo_screenwidth(),root.winfo_screenheight(),root.winfo_width(),root.winfo_height())
    app._close()
