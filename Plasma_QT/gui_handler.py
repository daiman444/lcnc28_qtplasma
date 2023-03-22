############################
# **** IMPORT SECTION **** #
############################

import os
import linuxcnc
from PyQt5 import QtCore, QtWidgets
from qtvcp.widgets.mdi_line import MDILine as MDI_WIDGET
from qtvcp.widgets.gcode_editor import GcodeEditor as GCODE
from qtvcp.widgets import gcode_graphics as GG
from qtvcp.widgets.stylesheeteditor import StyleSheetEditor as SSE
from qtvcp.lib.keybindings import Keylookup
from qtvcp.lib.aux_program_loader import Aux_program_loader
from qtvcp.core import Status, Action
from qtvcp import logger

LOG = logger.getLogger(__name__)
KEYBIND = Keylookup()
STATUS = Status()
ACTION = Action()
STYLEEDITOR = SSE()
AUX_PRGM = Aux_program_loader()
class HandlerClass:
    ########################
    # **** INITIALIZE **** #
    ########################
    # widgets allows access to  widgets from the qtvcp files
    # at this point the widgets and hal pins are not instantiated
    def __init__(self, halcomp, widgets, paths):
        self.hal = halcomp
        self.lcnc = linuxcnc
        self.inifile = self.lcnc.ini(INIPATH)
        self.stat = self.lcnc.stat
        self.cmd = linuxcnc.command()
        self.w = widgets
        self.PATHS = paths
        self.w.filedialog = True
        self.editor = self.inifile.find("DISPLAY", "EDITOR")
        self.loaded_file = False
        STATUS.connect('file-loaded', self.loaded_file_)

    ##########################################
    # Special Functions called from QTSCREEN
    ##########################################

    # at this point:
    # the widgets are instantiated.
    # the HAL pins are built but HAL is not set ready
    def initialized__(self):
        KEYBIND.add_call('Key_F12', 'on_keycall_F12')
        self.init_widgets()
        # self.w.label_2.setText(self.current_mode)

        # view section
        self.w.pb_view_z.clicked.connect(lambda w: self.view_action('z'))
        self.w.pb_view_clear.clicked.connect(lambda w: self.view_action('clear'))
        self.w.pb_view_zoom_in.clicked.connect(lambda w: self.view_action('zoom-in'))
        self.w.pb_view_zoom_out.clicked.connect(lambda w: self.view_action('zoom-out'))

        # other section
        self.w.pb_gcode_tab.clicked.connect(lambda w: self.sw_other('gcode'))
        self.w.pb_mdi_tab.clicked.connect(lambda w: self.sw_other('mdi'))
        self.w.pb_settings_tab.clicked.connect(lambda w: self.sw_other('settings'))

        # setting wizards
        self.w.pb_halshow.clicked.connect(lambda w: AUX_PRGM.load_halshow())
        self.w.pb_halscope.clicked.connect(lambda w: AUX_PRGM.load_halscope())
        self.w.pb_halmeter.clicked.connect(lambda w: AUX_PRGM.load_halmeter())
        self.w.pb_status.clicked.connect(lambda w: AUX_PRGM.load_status())
        self.w.pb_calibration.clicked.connect(lambda w: AUX_PRGM.load_calibration())

        # gcode section
        self.w.pb_gcode_load.clicked.connect(lambda w: self.actions_with_gcode('load'))
        self.w.pb_gcode_edit.clicked.connect(lambda w: self.actions_with_gcode('edit'))
        self.w.pb_gcode_reload.clicked.connect(lambda w: self.actions_with_gcode('reload'))


    def processed_key_event__(self, receiver, event, is_pressed, key, code, shift, cntrl):
        # when typing in MDI, we don't want keybinding to call functions
        # so, we catch and process the events directly.
        # We do want ESC, F1 and F2 to call keybinding functions though
        if code not in (QtCore.Qt.Key_Escape,
                        QtCore.Qt.Key_F1,
                        QtCore.Qt.Key_F2,
                        QtCore.Qt.Key_F3,
                        QtCore.Qt.Key_F5,
                        QtCore.Qt.Key_F5):

            # search for the top widget of whatever widget received the event
            # then check if it's one we want the keypress events to go to
            flag = False
            receiver2 = receiver
            while receiver2 is not None and not flag:
                if isinstance(receiver2, QtWidgets.QDialog):
                    flag = True
                    break
                if isinstance(receiver2, MDI_WIDGET):
                    flag = True
                    break
                if isinstance(receiver2, GCODE):
                    flag = True
                    break
                receiver2 = receiver2.parent()

            if flag:
                if isinstance(receiver2, GCODE):
                    # if in manual do our keybindings - otherwise
                    # send events to gcode widget
                    if not STATUS.is_man_mode():
                        if is_pressed:
                            receiver.keyPressEvent(event)
                            event.accept()
                        return True
                elif is_pressed:
                    receiver.keyPressEvent(event)
                    event.accept()
                    return True
                else:
                    event.accept()
                    return True

        if event.isAutoRepeat():
            return True

        # ok if we got here then try keybindings function calls
        # KEYBINDING will call functions from handler file as
        # registered by KEYBIND.add_call(KEY,FUNCTION) above
        return KEYBIND.manage_function_calls(self, event, is_pressed, key, shift, cntrl)

    ########################
    # callbacks from STATUS #
    ########################

    #######################
    # callbacks from form #
    #######################
    def init_widgets(self):
        self.w.sw_other.setCurrentIndex(0)


    def loaded_file_(self, w, file_prefs):
        if file_prefs:
            self.loaded_file = file_prefs
        return file_prefs

    def view_action(self, view):
        if view in ('z', 'clear', 'zoom-in', 'zoom-out'):
            STATUS.emit('graphics-view-changed', view, None)

    def sw_other(self, view):
        if view == 'gcode':
            self.w.sw_other.setCurrentIndex(0)
        if view == 'mdi':
            self.w.sw_other.setCurrentIndex(1)
        if view == 'settings':
            self.w.sw_other.setCurrentIndex(2)

    def actions_with_gcode(self, action):
        if action == 'load':
            STATUS.emit('dialog-request', {'NAME': 'LOAD', 'ID': None})
            self.loaded_file = self.stat.file
        elif action == 'edit':
            file = str(self.loaded_file)
            file = file.replace(' ', '\ ')
            editor = str(self.editor) + ' '
            ACTION.SET_MANUAL_MODE()
            os.system(editor + file)
        elif action == 'reload':
            ACTION.SET_AUTO_MODE()

    #####################
    # general functions #
    #####################

    # keyboard jogging from key binding calls
    # double the rate if fast is true
    def kb_jog(self, state, joint, direction, fast=False, linear=True):
        if not STATUS.is_man_mode() or not STATUS.machine_is_on():
            return
        if linear:
            distance = STATUS.get_jog_increment()
            rate = STATUS.get_jograte()/60
        else:
            distance = STATUS.get_jog_increment_angular()
            rate = STATUS.get_jograte_angular()/60
        if state:
            if fast:
                rate = rate * 2
            ACTION.JOG(joint, direction, rate, distance)
        else:
            ACTION.JOG(joint, 0, 0, 0)

    #####################
    # KEY BINDING CALLS #
    #####################

    # Machine control
    def on_keycall_ESTOP(self, event, state, shift, cntrl):
        if state:
            ACTION.SET_ESTOP_STATE(STATUS.estop_is_clear())

    def on_keycall_POWER(self, event, state, shift, cntrl):
        if state:
            ACTION.SET_MACHINE_STATE(not STATUS.machine_is_on())

    def on_keycall_HOME(self, event, state, shift, cntrl):
        if state:
            if STATUS.is_all_homed():
                ACTION.SET_MACHINE_UNHOMED(-1)
            else:
                ACTION.SET_MACHINE_HOMING(-1)

    def on_keycall_ABORT(self, event, state, shift, cntrl):
        if state:
            if STATUS.stat.interp_state == linuxcnc.INTERP_IDLE:
                self.w.close()
            else:
                self.cmnd.abort()

    def on_keycall_F12(self, event, state, shift, cntrl):
        if state:
            STYLEEDITOR.load_dialog()

    # Linear Jogging
    def on_keycall_XPOS(self, event, state, shift, cntrl):
        self.kb_jog(state, 0, 1, shift)

    def on_keycall_XNEG(self, event, state, shift, cntrl):
        self.kb_jog(state, 0, -1, shift)

    def on_keycall_YPOS(self, event, state, shift, cntrl):
        self.kb_jog(state, 1, 1, shift)

    def on_keycall_YNEG(self, event, state, shift, cntrl):
        self.kb_jog(state, 1, -1, shift)

    def on_keycall_ZPOS(self, event, state, shift, cntrl):
        self.kb_jog(state, 2, 1, shift)

    def on_keycall_ZNEG(self, event, state, shift, cntrl):
        self.kb_jog(state, 2, -1, shift)

    def on_keycall_APOS(self, event, state, shift, cntrl):
        pass
        # self.kb_jog(state, 3, 1, shift, False)

    def on_keycall_ANEG(self, event, state, shift, cntrl):
        pass
        # self.kb_jog(state, 3, -1, shift, linear=False)

    ###########################
    # **** closing event **** #
    ###########################

    ##############################
    # required class boiler code #
    ##############################

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        return setattr(self, item, value)

################################
# required handler boiler code #
################################


def get_handlers(halcomp, widgets, paths):
    return[HandlerClass(halcomp, widgets, paths)]


INIPATH = os.environ.get('INI_FILE_NAME', '/dev/null')
