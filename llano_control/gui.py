import copy
import json
import os
from pathlib import Path
import sys
import math
import threading
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk
from .core import load, save, validate, Preview, MODES, EFFECTS, rpm_step, AI_CURVES, effective_curve
from .devices import inventory, sensors
from .telemetry import Monitor
from .fan import FanController
from .thermal import control_temperature
from .power_position import load_position, save_position
from . import ui_i18n
from .i18n import t as tr, LANGUAGE, save_language, set_language

def fmt(value,digits=0):
    return '—' if value is None else f'{value:.{digits}f}'

class Gauge(Gtk.DrawingArea):
    def __init__(self,title,unit,maximum):
        super().__init__(); self.title=tr(title); self.unit=unit; self.maximum=maximum; self.value=None
        self.set_content_width(160); self.set_content_height(165); self.set_draw_func(self.draw)
    def update(self,value):
        # The gauge displays integers; sub-unit changes need no new frame.
        displayed=None if value is None else round(value)
        title=tr(self.title)
        if (displayed,title)==getattr(self,'last_frame',None): return
        self.last_frame=(displayed,title); self.value=displayed; self.queue_draw()
    def draw(self,area,cr,width,height):
        x=width/2; y=height/2-10; radius=min(width/2-16,57)
        cr.set_line_width(7); cr.set_source_rgb(.18,.12,.27); cr.arc(x,y,radius,0,math.tau); cr.stroke()
        if self.value is not None:
            cr.set_source_rgb(.71,.17,1); cr.arc(x,y,radius,-math.pi/2,-math.pi/2+math.tau*max(0,min(1,self.value/self.maximum))); cr.stroke()
        cr.set_line_width(1); cr.set_source_rgb(.36,.17,.6); cr.arc(x,y,radius-10,0,math.tau); cr.stroke()
        cr.select_font_face('Sans',0,1); cr.set_font_size(24); cr.set_source_rgb(.98,.95,1)
        text=fmt(self.value)+(' '+self.unit if self.value is not None else '')
        ext=cr.text_extents(text); cr.move_to(x-ext.width/2-ext.x_bearing,y+8); cr.show_text(tr(text))
        cr.select_font_face('Sans',0,0); cr.set_font_size(12); cr.set_source_rgb(.65,.61,.75)
        title=tr(self.title)
        ext=cr.text_extents(title); cr.move_to(x-ext.width/2,height-9); cr.show_text(title)

class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.llanocontrol.App')
        self.connect('activate', self.on_activate)
        self.connect('shutdown', self.cleanup_tray)

    def on_activate(self, app):
        if hasattr(self, 'win'): self.win.present(); return
        self.data=load(); self.preview=Preview(); self.monitor=Monitor(); self.busy=False; self.closed=False
        self.latest=None; self.gpu_id=self.data.get("display_gpu")
        self.startup_apply_pending=True; self.startup_rgb_pending=False
        self.fan_controller=None; self.fan_busy=False; self.rgb_busy=False; self.power_busy=False
        self.fan_explicit=False;self.pending_hardware_action=None
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="llano-sensors")
        self.timer=None; self.last_usb_scan=0
        self.win=Gtk.ApplicationWindow(application=self,title='Llano Control · V12 Ultra')
        self.win.set_default_size(1100,820)
        self.win.connect('close-request',self.on_close)
        css=Gtk.CssProvider(); css.load_from_path(str(Path(__file__).with_name('style.css')))
        Gtk.StyleContext.add_provider_for_display(self.win.get_display(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12); self.margins(outer,18)
        scroll=Gtk.ScrolledWindow(); scroll.set_child(outer); self.win.set_child(scroll)
        top=Gtk.Box(spacing=10); outer.append(top)
        title=self.label('LLANO CONTROL', 'brand'); title.set_hexpand(True); top.append(title)
        top.append(self.label('V12 ULTRA  /  LINUX','muted'))
        top.append(self.label('Idioma','muted'))
        self.language=Gtk.ComboBoxText()
        self.language.append('es','Español'); self.language.append('en','English')
        self.language.set_active_id(LANGUAGE)
        self.language.connect('changed',self.change_language); top.append(self.language)
        hide=ui_i18n.button(Gtk.Button,label=tr('Minimizar a bandeja')); hide.connect('clicked',self.hide_to_tray); top.append(hide)
        leave=ui_i18n.button(Gtk.Button,label=tr('Salir')); leave.connect('clicked',lambda *_: self.quit()); top.append(leave)
        columns=Gtk.Box(spacing=16); outer.append(columns)
        left=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14); left.set_hexpand(True); left.set_size_request(480,-1)
        right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14); right.set_hexpand(True); right.set_size_request(410,-1)
        columns.append(left); columns.append(right)
        hero=self.panel(left,'V12 Ultra Laptop Cooler'); hero.add_css_class('hero')
        hero_title=hero.get_first_child();hero.remove(hero_title)
        hero_body=Gtk.Grid(column_spacing=16,row_spacing=12);hero.append(hero_body)
        hero_body.attach(hero_title,0,0,2,1)
        hero_info=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        hero_info.set_size_request(-1,160)
        hero_info.set_hexpand(True);hero_body.attach(hero_info,0,1,1,1)
        self.status=self.label('Buscando conexión USB…');hero_info.append(self.status)
        hero_info.append(self.label('V12 ULTRA · USB HID','muted'))
        self.power_status=self.label('Control general: ventilador, RGB y pantalla.','muted');hero_info.append(self.power_status)
        switch_row=Gtk.Box(spacing=8);switch_row.set_halign(Gtk.Align.START)
        switch_row.set_valign(Gtk.Align.END);switch_row.set_vexpand(True)
        switch_row.set_margin_top(6);hero_info.append(switch_row)
        switch_row.append(self.label('Apagado','muted'))
        self.power_confirmed=load_position();self.power_switch_updating=False
        self.power_toggle=Gtk.Switch();self.power_toggle.set_valign(Gtk.Align.CENTER)
        self.power_toggle.set_active(self.power_confirmed is True)
        ui_i18n.bind(self.power_toggle,'set_tooltip_text','Encender/apagar Llano')
        self.power_toggle.connect('state-set',self.power_switch_changed);switch_row.append(self.power_toggle)
        switch_row.append(self.label('Encendido','muted'))
        from .product_image import image_bytes
        texture=Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_bytes()))
        picture=Gtk.Picture.new_for_paintable(texture)
        picture.set_can_shrink(True);picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        picture.set_size_request(180,160);picture.set_valign(Gtk.Align.CENTER)
        picture.set_alternative_text('Llano V12 Ultra');hero_body.attach(picture,1,0,1,2)
        hardware=self.panel(left,'Hardware Status')
        self.cpu_title=self.label('CPU','section'); hardware.append(self.cpu_title)
        self.cpu_gauges=self.metric_pair(hardware)
        self.cpu_detail=self.label('Frecuencia — MHz  ·  Potencia — W','muted'); hardware.append(self.cpu_detail)
        hardware.append(Gtk.Separator())
        self.gpu_choice=ui_i18n.ComboBoxText(); self.gpu_choice.connect('changed',self.select_gpu); hardware.append(self.gpu_choice)
        self.gpu_gauges=self.metric_pair(hardware)
        self.gpu_detail=self.label('Frecuencia — MHz  ·  Potencia — W','muted'); hardware.append(self.gpu_detail)
        self.intel_detail=self.label('','muted'); hardware.append(self.intel_detail)
        self.ram_bar=self.memory_bar(hardware,'DRAM'); self.vram_bar=self.memory_bar(hardware,'VRAM')
        self.telemetry_status=self.label('Leyendo sensores…','muted'); hardware.append(self.telemetry_status)
        self.fields={}
        rpm=self.panel(right,'RPM Mode')
        self.fields['mode']=self.combo(MODES); self.fields['mode'].set_visible(False); rpm.append(self.fields['mode'])
        modes=Gtk.Grid(column_spacing=8,row_spacing=8,column_homogeneous=True); rpm.append(modes); self.mode_buttons={}
        for i,(key,title) in enumerate([('Low','AI Low'),('Medium','AI Medium'),('High','AI High'),('Custom','Custom'),('Manual','Manual')]):
            button=ui_i18n.button(Gtk.ToggleButton,label=tr(title)); button.set_size_request(-1,52)
            button.connect('clicked',self.choose_mode,key); self.mode_buttons[key]=button; modes.attach(button,i%3,i//3,1,1)
        self.mode_range=self.label('','muted'); rpm.append(self.mode_range)
        self.fields['mode'].connect('changed',self.mode_changed)
        self.fields['temperature_source']=ui_i18n.ComboBoxText()
        for key,label in (('cpu','CPU'),('gpu','GPU'),('both','CPU + GPU')):
            self.fields['temperature_source'].append(key,tr(label))
        self.row(rpm,'Temperatura para las RPM',self.fields['temperature_source'])
        self.control_gpu=ui_i18n.ComboBoxText()
        self.control_gpu.append('',tr('GPU más caliente disponible'));self.control_gpu.set_active_id('')
        self.row(rpm,'GPU de control',self.control_gpu)
        rpm.append(self.label('CPU + GPU usa la mayor temperatura disponible.','muted'))
        self.fields['manual_thermal']=Gtk.CheckButton()
        self.row(rpm,'Manual según temperatura · RPM como máximo',self.fields['manual_thermal'])
        self.fields['manual_thermal'].connect('toggled',lambda *_: self.graph.queue_draw() if hasattr(self,'graph') else None)
        self.fields['rpm']=Gtk.SpinButton.new_with_range(300,2800,100)
        self.fields['rpm'].set_increments(100,100)
        self.fields['rpm'].set_snap_to_ticks(True)
        self.fields['rpm'].connect('value-changed',lambda *_: self.graph.queue_draw() if hasattr(self,'graph') else None)
        self.row(rpm,'Objetivo manual · RPM',self.fields['rpm'])
        self.fields['power']=Gtk.CheckButton(); self.row(rpm,'Solicitar encendido al aplicar',self.fields['power'])
        self.fields['hysteresis']=Gtk.SpinButton.new_with_range(0,10,1); self.row(rpm,'Histéresis · °C',self.fields['hysteresis'])
        rpm.append(self.label('Aplicar modo activa el control. Rangos RPM estimados; calibración pendiente en los extremos.','muted'))
        curvebox=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        exp=ui_i18n.button(Gtk.Expander,label=tr('Speed Settings · curva y sensor CPU')); exp.set_child(curvebox); rpm.append(exp)
        self.sensor=ui_i18n.ComboBoxText(); curvebox.append(self.sensor)
        self.curve=Gtk.Entry(); self.curve.set_placeholder_text('30:600, 50:1000, 70:1800, 90:2800'); curvebox.append(self.curve)
        self.graph=Gtk.DrawingArea(); self.graph.set_content_height(160); self.graph.set_draw_func(self.draw); curvebox.append(self.graph)
        self.curve.connect('changed',lambda *_: self.graph.queue_draw())
        rgb=self.panel(right,'RGB Lighting Control')
        self.fields['rgb']=Gtk.CheckButton(); self.row(rgb,'Iluminación',self.fields['rgb'])
        self.fields['effect']=self.combo(EFFECTS); self.row(rgb,'Mode',self.fields['effect'])
        self.fields['color']=ui_i18n.ComboBoxText()
        for color,label in (('#ff3355','Rojo'),('#3985ff','Azul'),('#38dc8c','Verde'),('#aa55ff','Lila'),('#ffcf40','Naranja')):
            self.fields['color'].append(color,tr(label))
        self.row(rgb,'Color',self.fields['color'])
        for key,title,maximum in [('brightness','Brillo · 0–255',255),('animation_speed','Velocidad · 0–3',3)]:
            self.fields[key]=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,maximum,1)
            self.fields[key].set_draw_value(True); self.fields[key].set_digits(0); self.fields[key].set_hexpand(True)
            self.row(rgb,title,self.fields[key])
        rgb.append(self.label('Velocidad 0: animación lenta. Colores predefinidos del dispositivo.','muted'))
        self.rgb_apply=ui_i18n.button(Gtk.Button,label=tr('Aplicar RGB'))
        self.rgb_apply.connect('clicked',self.apply_rgb); rgb.append(self.rgb_apply)
        self.rgb_status=self.label('RGB se aplica bajo demanda; no cambia RPM ni encendido general.','muted'); rgb.append(self.rgb_status)
        profile=self.panel(outer,'Perfiles y aplicación')
        line=Gtk.Box(spacing=8); profile.append(line)
        self.profiles=Gtk.ComboBoxText(); line.append(self.profiles)
        self.name=Gtk.Entry(); self.name.set_hexpand(True); ui_i18n.bind(self.name,'set_placeholder_text','Nombre de perfil'); line.append(self.name)
        for label,callback in [('Guardar',self.store),('Previsualizar',self.simulate),('Diagnóstico',self.export)]:
            b=ui_i18n.button(Gtk.Button,label=tr(label)); b.connect('clicked',callback); line.append(b)
        self.apply_button=ui_i18n.button(Gtk.Button,label=tr('Aplicar modo y RPM'))
        self.apply_button.connect('clicked',self.apply_mode); profile.append(self.apply_button)
        self.fan_stop=ui_i18n.button(Gtk.Button,label=tr('Detener control automático'))
        self.fan_stop.connect('clicked',self.stop_fan); profile.append(self.fan_stop)
        self.fan_status=self.label('Control del ventilador inactivo.','muted'); profile.append(self.fan_status)
        self.auto=ui_i18n.button(Gtk.CheckButton,label=tr('Abrir al iniciar sesión')); self.auto.set_active(self.auto_path().exists()); self.auto.connect('toggled',self.autostart); profile.append(self.auto)
        self.message=self.label('Guardar conserva el perfil; Aplicar RGB envía la iluminación al dispositivo.','muted'); profile.append(self.message)
        self.result=self.label(''); profile.append(self.result)
        self.profiles.connect('changed',self.select_profile)
        self.refresh_profiles(); self.refresh(); self.tick()
        self.win.connect("map",self.window_mapped)
        self.startup_pending=True
        self.start_tray()
        self.startup_timer=GLib.timeout_add_seconds(8,self.finish_startup)

    def hardware_busy(self):
        return self.fan_busy or self.rgb_busy or self.power_busy

    def update_hardware_buttons(self):
        available=not (self.rgb_busy or self.power_busy or getattr(self,"fan_explicit",False) or getattr(self,"pending_hardware_action",None))
        for button in (self.apply_button,self.fan_stop,self.rgb_apply,self.power_toggle):
            if button.get_sensitive()!=available:button.set_sensitive(available)

    def defer_during_fan(self,callback,*args):
        if self.fan_busy and not getattr(self,'fan_explicit',False):
            self.pending_hardware_action=(callback,args)
            self.update_hardware_buttons()
            return True
        return False

    def set_device_power(self,button,enabled=None):
        if self.defer_during_fan(self.set_device_power,button,enabled):return
        if self.hardware_busy():return
        # Explicit power changes pause the local curve before queuing USB work.
        if self.fan_controller:self.fan_controller.active=False
        self.fan_status.set_text(tr('Control automático pausado. Pulsa Aplicar modo para reanudar.'))
        self.power_busy=True;self.update_hardware_buttons()
        self.power_status.set_text(tr('Cambiando encendido general…'))
        def worker():
            try:
                process=subprocess.run([sys.executable,'-m','llano_control.fan',
                                        json.dumps({'operation':'toggle_power'} if enabled is None else {'operation':'power','enabled':enabled})],
                                       capture_output=True,text=True,timeout=8)
                if process.returncode:raise OSError(process.stderr.strip() or 'USB error')
                result=json.loads(process.stdout)
                if enabled is not None and result['power'] is not enabled:raise ValueError('Power state mismatch')
                message='Llano encendido · estado USB confirmado.' if result['power'] else 'Llano apagado · estado USB confirmado.'
                confirmed=result['power']
            except (OSError,ValueError,KeyError,subprocess.TimeoutExpired) as error:
                message='No se pudo confirmar el encendido: '+str(error);confirmed=None
            GLib.idle_add(self.power_finished,message,confirmed)
        self.executor.submit(worker)

    def power_finished(self,message,confirmed=None):
        self.power_busy=False
        if not self.closed:
            self.update_hardware_buttons();self.power_status.set_text(tr(message))
            self.update_power_indicator(confirmed)
        return False

    def power_switch_changed(self,widget,enabled):
        if not self.power_switch_updating:
            self.set_device_power(widget,enabled)
        return True

    def update_power_indicator(self,confirmed):
        if confirmed is not None:
            if confirmed!=self.power_confirmed:
                try:save_position(confirmed)
                except OSError:
                    self.power_status.set_text(tr('Estado confirmado; no se pudo guardar la posición.'))
            self.power_confirmed=confirmed
        self.power_switch_updating=True
        try:
            active=self.power_confirmed is True
            if self.power_toggle.get_active()!=active:self.power_toggle.set_active(active)
            if self.power_toggle.get_state()!=active:self.power_toggle.set_state(active)
        finally:self.power_switch_updating=False

    def sync_power_position(self):
        if self.hardware_busy():return
        self.power_busy=True;self.update_hardware_buttons()
        def worker():
            try:
                result=subprocess.run([sys.executable,'-m','llano_control.fan',json.dumps({'operation':'read_power'})],
                                      capture_output=True,text=True,timeout=8)
                if result.returncode:raise OSError(result.stderr.strip())
                confirmed=json.loads(result.stdout)['power']
                if type(confirmed) is not bool:raise ValueError('Invalid power state')
                message='Llano encendido · estado USB confirmado.' if confirmed else 'Llano apagado · estado USB confirmado.'
            except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):
                confirmed=None;message='Posición recordada; estado del dispositivo sin confirmar.'
            GLib.idle_add(self.power_finished,message,confirmed)
        self.executor.submit(worker)

    def apply_mode(self,*_):
        if self.defer_during_fan(self.apply_mode):return
        if self.hardware_busy():return
        try:
            _,profile=self.collect()
            self.fan_controller=FanController(profile)
            self.drive_fan(self.latest or {})
        except (ValueError,KeyError,TypeError) as error:
            self.fan_status.set_text(tr(str(error)))

    def stop_fan(self,*_):
        self.pending_hardware_action=None
        if self.fan_controller:self.fan_controller.active=False
        self.fan_status.set_text(tr('Control detenido; se conserva la última velocidad.'))

    def drive_fan(self,sample):
        controller=self.fan_controller
        if not controller or not controller.active or self.hardware_busy():return
        now=time.monotonic()
        if now<controller.next_due:return
        temp,source=control_temperature(controller.profile,sample)
        controller.temperature_label=source+' · '+fmt(temp)+' °C'
        try:job=controller.plan(temp,now)
        except ValueError as error:
            self.fan_status.set_text(tr(str(error)));return
        if job is None:return
        self.fan_busy=True;self.fan_explicit=job['take_control']
        if self.fan_explicit:
            self.update_hardware_buttons()
            self.fan_status.set_text(tr('Aplicando consigna del ventilador…'))
        def worker():
            if not controller.active:
                GLib.idle_add(self.fan_finished,controller,None,None);return
            try:
                process=subprocess.run([sys.executable,'-m','llano_control.fan',json.dumps(job)],
                                       capture_output=True,text=True,timeout=8)
                if process.returncode:raise OSError(process.stderr.strip() or 'USB error')
                result=json.loads(process.stdout);error=None
            except (OSError,ValueError,subprocess.TimeoutExpired) as failure:
                result=None;error=str(failure)
            GLib.idle_add(self.fan_finished,controller,result,error)
        self.executor.submit(worker)

    def fan_finished(self,controller,result,error):
        self.fan_busy=False;self.fan_explicit=False
        if self.closed:return False
        pending=getattr(self,'pending_hardware_action',None)
        self.pending_hardware_action=None
        if pending:
            callback,args=pending
            GLib.idle_add(callback,*args)
        self.update_hardware_buttons()
        if controller is not self.fan_controller or not controller.active:return False
        if error:
            controller.active=False
            self.fan_status.set_text(tr('Control pausado: ')+str(error));return False
        controller.completed(result)
        if 'power' in result:self.update_power_indicator(result['power'])
        if result.get('paused'):
            self.fan_status.set_text(tr('Control pausado: mando físico o dispositivo apagado.'))
        elif not result['power']:
            self.fan_status.set_text(tr('Dispositivo apagado; control automático detenido.'))
        else:
            self.fan_status.set_text(tr('Consigna confirmada: ')+str(result['percent'])+' % · '+tr(controller.profile['mode'])+' · '+tr(getattr(controller,'temperature_label','')))
        return False

    def apply_rgb(self,*_):
        if self.defer_during_fan(self.apply_rgb):return
        if self.hardware_busy():return
        settings={k:(self.fields[k].get_active() if k=='rgb' else
                     round(self.fields[k].get_value()) if k in ('brightness','animation_speed') else
                     self.fields[k].get_active_id())
                  for k in ('rgb','effect','color','brightness','animation_speed')}
        self.rgb_busy=True;self.update_hardware_buttons()
        self.rgb_status.set_text(tr('Aplicando RGB…'))
        def worker():
            try:
                result=subprocess.run([sys.executable,'-m','llano_control.rgb',json.dumps(settings)],
                                      capture_output=True,text=True,timeout=8)
                message=('RGB confirmado por el dispositivo.' if result.returncode==0 else
                         'Error RGB: '+(result.stderr.strip() or result.stdout.strip()))
            except subprocess.TimeoutExpired:
                message='Tiempo de espera agotado. Comprueba el dispositivo antes de reintentar.'
            except OSError as error: message='Error RGB: '+str(error)
            GLib.idle_add(self.rgb_finished,message)
        self.executor.submit(worker)

    def rgb_finished(self,message):
        self.rgb_busy=False
        if not self.closed:
            self.update_hardware_buttons(); self.rgb_status.set_text(tr(message))
        return False

    def change_language(self,widget):
        try:
            language=widget.get_active_id()
            save_language(language)
            set_language(language)
            ui_i18n.refresh()
            for gauge in self.cpu_gauges+self.gpu_gauges: gauge.queue_draw()
            self.graph.queue_draw()
            data=dict(getattr(self,'last_tray_data',None) or {})
            self.send_tray(data)
        except OSError as error:
            self.message.set_text(tr(str(error)))

    def margins(self,widget,size):
        for side in ('top','bottom','start','end'): getattr(widget,'set_margin_'+side)(size)

    def label(self,text,style=None):
        label=ui_i18n.Label(label=tr(text),xalign=0,wrap=True)
        if style: label.add_css_class(style)
        return label

    def panel(self,parent,title):
        panel=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12); panel.add_css_class('panel'); self.margins(panel,0)
        panel.append(self.label(title,'section')); parent.append(panel); return panel

    def row(self,box,label,widget):
        row=Gtk.Box(spacing=12); text=self.label(label); text.set_hexpand(True)
        row.append(text); widget.set_size_request(150,-1); row.append(widget); box.append(row)

    def metric_pair(self,box):
        line=Gtk.Box(spacing=18); box.append(line)
        gauges=[Gauge('Carga','%',100),Gauge('Temperatura','°C',110)]
        for g in gauges: g.set_hexpand(True); line.append(g)
        return gauges

    def memory_bar(self,box,name):
        label=self.label(name+' —','muted'); box.append(label)
        bar=Gtk.ProgressBar(); box.append(bar); return label,bar,name

    def choose_mode(self,button,key):
        self.fields['mode'].set_active_id(key)
        self.mode_changed()

    def mode_changed(self,*_):
        mode=self.fields['mode'].get_active_id()
        for key,button in self.mode_buttons.items(): button.set_active(key==mode)
        self.fields['rpm'].set_sensitive(mode=='Manual')
        curve=AI_CURVES.get(mode)
        self.mode_range.set_text(f'{curve[0][1]}–{curve[-1][1]} RPM · 30–90 °C' if curve else '')
        self.curve.set_sensitive(mode=='Custom')
        self.graph.queue_draw()

    def populate_control_gpus(self,sample,wanted=None):
        if wanted is None:wanted=self.control_gpu.get_active_id() or ''
        choices=[('',tr('GPU más caliente disponible'))]+[(g['id'],g['name']) for g in sample.get('gpus',[])]
        if wanted and wanted not in [key for key,_ in choices]:choices.append((wanted,tr('GPU no disponible')+' · '+wanted))
        if choices!=getattr(self,'control_gpu_choices',None):
            self.control_gpu_choices=choices;self.control_gpu.remove_all()
            for key,label in choices:self.control_gpu.append(key,label)
        self.control_gpu.set_active_id(wanted)

    def select_gpu(self,*_):
        self.gpu_id=self.gpu_choice.get_active_id()
        if self.latest: self.render_metrics(self.latest)

    def window_mapped(self,*_):
        if self.closed: return
        self.sync_power_position()
        if self.latest: self.render_metrics(self.latest)
        if not self.busy:
            if self.timer: GLib.source_remove(self.timer); self.timer=None
            self.tick()

    def tick(self):
        self.timer=None
        if self.closed: return False
        if not self.busy:
            self.busy=True
            self.sample_started=time.monotonic()
            lightweight=not self.win.get_visible()
            def worker():
                try: sample=self.monitor.sample(lightweight=lightweight)
                except Exception as e: sample={'error':str(e)}
                GLib.idle_add(self.receive,sample)
            self.executor.submit(worker)
        return False

    def receive(self,sample):
        self.busy=False
        if self.closed: return False
        interval=1 if self.win.get_visible() else 2
        delay=max(100,round(1000*(interval-(time.monotonic()-self.sample_started))))
        self.timer=GLib.timeout_add(delay,self.tick)
        if 'error' not in sample:
            self.latest=sample
            App.apply_saved_on_startup(self)
        self.drive_fan(sample)
        if 'error' in sample:
            self.latest=None
            self.send_tray({'cpu':None,'gpu':None,'gpu_name':'Lectura no disponible'})
            if not self.win.get_visible(): return False
            self.intel_detail.set_text(tr(''))
            self.telemetry_status.set_text(tr('Lectura no disponible: '+sample['error']))
            for gauge in self.cpu_gauges+self.gpu_gauges: gauge.update(None)
            for label,bar,name in (self.ram_bar,self.vram_bar): label.set_text(tr(name+' —')); bar.set_fraction(0)
            self.cpu_detail.set_text(tr('Frecuencia — MHz · Potencia — W')); self.gpu_detail.set_text(tr('Frecuencia — MHz · Potencia — W'))
            return False
        self.latest=sample
        if not self.win.get_visible():
            gpu=next((g for g in sample['gpus'] if g['id']==self.gpu_id), sample['gpus'][0] if sample['gpus'] else {})
            self.send_tray({'cpu':sample['cpu'].get('temp'),'gpu':gpu.get('temp'),'gpu_name':gpu.get('name','No disponible')})
            return False
        self.populate_control_gpus(sample)
        ids=[g['id'] for g in sample['gpus']]
        if ids!=getattr(self,'gpu_ids',None):
            self.gpu_ids=ids; wanted=self.gpu_id; self.gpu_choice.remove_all()
            for g in sample['gpus']: self.gpu_choice.append(g['id'],tr(g['name']))
            if not ids: self.gpu_choice.append('',tr('GPU · No disponible'))
            self.gpu_choice.set_active_id(wanted if wanted in ids else (ids[0] if ids else ''))
        self.render_metrics(sample)
        if time.monotonic()-self.last_usb_scan>=30: self.refresh()
        return False

    def render_metrics(self,sample):
        cpu=sample['cpu']; gpu=next((g for g in sample['gpus'] if g['id']==self.gpu_id),{})
        self.send_tray({'cpu':cpu.get('temp'),'gpu':gpu.get('temp'),'gpu_name':gpu.get('name','No disponible')})
        self.cpu_detail.set_tooltip_text(tr(cpu.get('power_source','Potencia no disponible')))
        self.cpu_title.set_text(tr(cpu['name'])); self.cpu_title.set_tooltip_text(tr(cpu.get('temp_source')))
        for metrics,gauges,detail in [(cpu,self.cpu_gauges,self.cpu_detail),(gpu,self.gpu_gauges,self.gpu_detail)]:
            gauges[0].title=tr(metrics.get('load_label','Carga'))
            gauges[0].update(metrics.get('load')); gauges[1].update(metrics.get('temp'))
            detail.set_text(tr('Frecuencia '+fmt(metrics.get('freq'))+' MHz  ·  '+metrics.get('power_label','Potencia')+' '+fmt(metrics.get('power'),1)+' W'))
        for values,(label,bar,name) in [(sample['ram'],self.ram_bar),(gpu.get('memory',{}),self.vram_bar)]:
            label.set_text(tr(name+'   '+fmt(values.get('load'))+' %     '+fmt(values.get('used'),1)+' / '+fmt(values.get('total'),1)+' GiB'))
            fraction=round(max(0,min(1,(values.get('load') or 0)/100)),3)
            if bar.get_fraction()!=fraction: bar.set_fraction(fraction)
        if gpu.get('memory',{}).get('shared') and gpu['memory'].get('total') is None:
            self.vram_bar[0].set_text(tr('Memoria Intel: compartida con RAM · uso dedicado no expuesto'))
        client=gpu.get('client_metrics',{})
        gts=' · '.join(f'{k.upper()}: {v} MHz' for k,v in sorted(gpu.get('gt_frequencies',{}).items()))
        engines=' · '.join(f'{k}: {v:.1f} %' for k,v in sorted(client.get('engines',{}).items()))
        extra=[]
        if gpu.get('source')=='amdgpu / hwmon':
            extra.append(' · '.join(f'{k}: {v:.1f} °C' for k,v in gpu.get('temperatures',{}).items()))
            if gpu.get('memory_frequency') is not None: extra.append('Reloj memoria: '+fmt(gpu['memory_frequency'])+' MHz')
            if gpu.get('gtt_used') is not None: extra.append('GTT (RAM): '+fmt(gpu['gtt_used'],2)+' / '+fmt(gpu.get('gtt_total'),2)+' GiB')
        self.intel_detail.set_text(tr('\n'.join(v for v in [gts,engines]+extra if v)))
        if client.get('resident_bytes') is not None:
            self.vram_bar[0].set_text(tr(f"RAM GPU residente (clientes): {client['resident_bytes']/1048576:.2f} MiB · {client['clients']} cliente(s)"))
            self.vram_bar[0].set_tooltip_text(tr('Suma por cliente accesible, no uso global; buffers compartidos pueden duplicarse. Solicitada: '+fmt(client.get('allocated_bytes')/1048576 if client.get('allocated_bytes') is not None else None,2)+' MiB'))
        else: self.vram_bar[0].set_tooltip_text(tr(None))
        self.gpu_detail.set_tooltip_text(tr(gpu.get('note',gpu.get('source',''))))
        self.telemetry_status.set_text(tr(' · '.join(sample['errors']+([gpu['note']] if gpu.get('note') else [])) or 'Ahorro: 1 s visible / 2 s en bandeja · — = dato no disponible'))

    def start_tray(self):
        self.tray_connected=False; self.tray=None
        try:
            self.tray=subprocess.Popen([sys.executable,str(Path(__file__).with_name('tray_helper.py'))],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1)
            os.set_blocking(self.tray.stdin.fileno(),False)
            def reader():
                for line in self.tray.stdout:
                    try: event=json.loads(line)
                    except ValueError: continue
                    GLib.idle_add(self.tray_event,event)
                GLib.idle_add(self.tray_event,{'event':'connection','connected':False})
            threading.Thread(target=reader,daemon=True).start()
        except OSError:
            self.message.set_text(tr('Bandeja no disponible. La ventana seguirá abierta.'))

    def tray_event(self,event):
        if self.closed: return False
        kind=event.get('event')
        if kind=='show': self.win.present()
        elif kind=='quit': self.quit()
        elif kind=='connection':
            self.tray_connected=bool(event.get('connected'))
            if self.tray_connected: self.startup_pending=False
            if not self.tray_connected and not getattr(self,'startup_pending',False) and not self.win.get_visible():
                self.win.present()
                self.message.set_text(tr('La bandeja se desconectó; se ha restaurado la ventana.'))
        return False

    def finish_startup(self):
        self.startup_timer=None
        if self.closed: return False
        self.startup_pending=False
        if not self.tray_connected:
            self.win.present()
            self.message.set_text(tr('No hay bandeja disponible; se muestra la ventana para poder acceder a la aplicación.'))
        return False

    def send_tray(self,data):
        data={**data,'language':self.language.get_active_id()}
        for key in ('cpu','gpu'):
            if data.get(key) is not None: data[key]=round(data[key])
        tray=getattr(self,'tray',None)
        if tray is None or tray.poll() is not None: return
        if data==getattr(self,'last_tray_data',None): return
        try:
            os.write(tray.stdin.fileno(),(json.dumps(data)+'\n').encode())
            self.last_tray_data=data
        except (OSError,ValueError): pass

    def hide_to_tray(self,*_):
        App.persist_current(self)
        if getattr(self,'tray_connected',False): self.win.set_visible(False)
        else:
            self.message.set_text(tr('No hay bandeja disponible. En Hyprland activa el módulo tray de Waybar. Dependencia: gir1.2-ayatanaappindicator3-0.1.'))

    def on_close(self,*_):
        self.hide_to_tray()
        return True

    def cleanup_tray(self,*_):
        App.persist_current(self)
        self.closed=True
        if getattr(self,"fan_controller",None):self.fan_controller.active=False
        if getattr(self,'timer',None): GLib.source_remove(self.timer)
        if hasattr(self,'executor'): self.executor.shutdown(wait=False,cancel_futures=True)
        if getattr(self,'startup_timer',None): GLib.source_remove(self.startup_timer)
        tray=getattr(self,'tray',None)
        if tray is not None:
            try: tray.stdin.close()
            except OSError: pass
            try: tray.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                tray.terminate()
                try: tray.wait(timeout=.5)
                except subprocess.TimeoutExpired: tray.kill(); tray.wait(timeout=.5)

    def combo(self, values):
        w=ui_i18n.ComboBoxText()
        for v in values: w.append(v,tr(v))
        return w

    def refresh_profiles(self):
        self.profiles.remove_all()
        for name in self.data['profiles']: self.profiles.append(name,name)
        self.profiles.set_active_id(self.data['active'])

    def select_profile(self, *_):
        name=self.profiles.get_active_id()
        if not name: return
        p=self.data['profiles'][name]; self.name.set_text(name); self.preview=Preview()
        if p['color'] not in [row[1] for row in self.fields['color'].get_model()]:
            self.fields['color'].append(p['color'],p['color'])
        for k,w in self.fields.items():
            if isinstance(w,(Gtk.SpinButton,Gtk.Scale)):
                value=rpm_step(p[k]) if k=='rpm' else p[k]
                if p.get('rgb_units')!='native':
                    if k=='brightness': value=round(value*255/100)
                    elif k=='animation_speed': value=round(value*3/100)
                w.set_value(value)
            elif isinstance(w,Gtk.CheckButton): w.set_active(p.get(k,True) if k=='manual_thermal' else p[k])
            elif isinstance(w,Gtk.ComboBoxText): w.set_active_id(p.get(k,'cpu') if k=='temperature_source' else p[k])
            else: w.set_text(p[k])
        self.populate_control_gpus(self.latest or {},p.get('control_gpu',''))
        self.curve.set_text(', '.join(f'{t}:{r}' for t,r in p['curve']))
        self.sensor.remove_all(); self.sensor.append('', tr('CPU del sistema · automático'))
        values=sensors()
        for key,value in values.items(): self.sensor.append(key,tr(value['label']))
        if p['sensor'] and p['sensor'] not in values: self.sensor.append(p['sensor'],tr('Sensor desconectado'))
        self.sensor.set_active_id(p['sensor']); self.graph.queue_draw(); self.mode_changed()

    def collect(self):
        p={}
        for k,w in self.fields.items():
            if isinstance(w,(Gtk.SpinButton,Gtk.Scale)): p[k]=round(w.get_value())
            elif isinstance(w,Gtk.CheckButton): p[k]=w.get_active()
            elif isinstance(w,Gtk.ComboBoxText): p[k]=w.get_active_id()
            else: p[k]=w.get_text()
        p['control_gpu']=self.control_gpu.get_active_id() or ''
        p['rgb_units']='native'
        p['sensor']=self.sensor.get_active_id() or ''
        p['curve']=[list(map(float,part.strip().split(':'))) for part in self.curve.get_text().split(',')]
        p['rpm']=rpm_step(p['rpm'])
        p['curve']=[[t,rpm_step(r)] for t,r in p['curve']]
        name=self.name.get_text().strip()
        validate({'version':1,'active':name,'profiles':{name:p}})
        return name,p

    def persist_current(self):
        # Saving does not refresh widgets or disturb an active controller snapshot.
        if not hasattr(self,'fields'): return True
        try:
            name,profile=self.collect()
            updated=copy.deepcopy(self.data)
            updated['profiles'][name]=profile;updated['active']=name
            updated['display_gpu']=self.gpu_id
            if updated!=self.data:
                save(updated);self.data=updated
            return True
        except (ValueError,KeyError,TypeError,OSError) as error:
            message=tr('No se pudieron guardar los ajustes: ')+str(error)
            self.message.set_text(message)
            print(message,file=sys.stderr)
            return False

    def apply_saved_on_startup(self):
        # Sensor delivery drives this once, including when startup stays in the tray.
        # A failed operation is not retried automatically.
        if self.closed or self.hardware_busy(): return
        if getattr(self,'startup_apply_pending',False):
            self.startup_apply_pending=False
            self.startup_rgb_pending=True
            self.apply_mode()
        if getattr(self,'startup_rgb_pending',False) and not self.hardware_busy():
            self.startup_rgb_pending=False
            self.apply_rgb()

    def store(self,*_):
        try:
            name,p=self.collect(); updated=copy.deepcopy(self.data); updated['profiles'][name]=p; updated['active']=name
            save(updated); self.data=updated; self.refresh_profiles(); self.message.set_text(tr('Perfil guardado en este equipo. No aplicado al hardware.'))
        except (ValueError,KeyError,TypeError,OSError) as e: self.message.set_text(tr(str(e)))

    def simulate(self,*_):
        try:
            _,p=self.collect(); temp,_=control_temperature(p,self.latest or {})
            rpm=Preview().calculate(p,temp)
            self.result.set_text(tr(f'Previsualización: {rpm} RPM objetivo · temperatura {temp} °C · ninguna escritura USB' if rpm is not None else 'Sin objetivo calculable: apagado solicitado o sensor no disponible. Sin acción USB.'))
            self.graph.queue_draw()
        except (ValueError,KeyError,TypeError) as e: self.message.set_text(tr(str(e)))

    def draw(self,area,cr,width,height):
        try: _,p=self.collect()
        except (ValueError,KeyError,TypeError,AttributeError): return
        cr.set_source_rgb(.15,.16,.20); cr.paint(); cr.set_source_rgb(.65,.4,1); cr.set_line_width(2)
        for i,(t,r) in enumerate(effective_curve(p)):
            x=20+t/110*(width-40); y=height-20-(r-300)/2500*(height-40)
            (cr.move_to if i==0 else cr.line_to)(x,y)
        cr.stroke(); cr.set_source_rgb(.9,.9,.9); cr.move_to(20,15); cr.show_text(tr('Curva local: 0–110 °C / 300–2800 RPM'))

    def refresh(self):
        self.last_usb_scan=time.monotonic()
        found=inventory(); candidates=[d for d in found['usb'] if d['candidate']]
        self.status.set_text(tr('USB conectado · identidad candidata' if candidates else 'USB desconectado / no visible'))
        return True

    def export(self,*_):
        try:
            folder=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'llano-control'; folder.mkdir(parents=True,exist_ok=True)
            path=folder/'diagnostic.json'; path.write_text(json.dumps(inventory(),indent=2,ensure_ascii=False))
            self.message.set_text(tr(f'Diagnóstico local: {path}'))
        except OSError as e: self.message.set_text(tr(str(e)))

    def auto_path(self):
        return Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'autostart/io.github.llanocontrol.App.desktop'

    def autostart(self,*_):
        try:
            path=self.auto_path()
            if self.auto.get_active():
                launcher=Path(__file__).resolve().parent.parent/'llano-control'
                # Desktop Exec quoting follows the desktop-entry specification.
                escaped=str(launcher).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('[Desktop Entry]\nType=Application\nName=Llano Control\nExec="'+escaped+'" gui\nTerminal=false\n')
            else: path.unlink(missing_ok=True)
        except OSError as e: self.message.set_text(tr(str(e)))

def run():
    from gi.repository import Gdk
    Gtk.init()
    if Gdk.Display.get_default() is None:
        print('No hay sesión gráfica disponible. Ejecuta la GUI dentro de Wayland/X11.', file=sys.stderr)
        return 1
    return App().run([sys.argv[0]])
