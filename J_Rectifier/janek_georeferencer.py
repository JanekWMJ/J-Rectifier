# -*- coding: utf-8 -*-
"""
/***************************************************************************
 J_Rectifier
                                 A QGIS plugin
 a
                              -------------------
        begin                : 2017-01-18
        git sha              : $Format:%H$
        copyright            : (C) 2017 by a
        email                : a
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import *
from PyQt4.QtGui import * #JANEK
from PyQt4 import *
from qgis.core import *
from qgis.gui import *
from osgeo import ogr, gdal, osr #JANEK
import qgis.utils
import numpy as np #JANEK
import math
import janek_transformations #JANEK importing stuff from other .py file
import datetime ##JANEK to aviod bugs tempfiles are named using the time of process YYYYmmdd_HHMMSS
import tempfile #JANEK: Added to find path of temp files on computer
import processing #JANEK 
from PyQt4 import QtGui
from PyQt4.QtWebKit import * #JANEK for creating html raport (that can be later convertet to pdf)
# Initialize Qt resources from file resources.py
import resources
#from gui import MainWindow
import os.path
from shutil import copyfile
from matplotlib import pyplot as plt
import sys

jg_running = 0 #JANEK variable that prevent from opening more than 1 plugin window

class JanekGeoreferencer:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'JRectifier_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)


        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&J Rectifier')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'JRectifier')
        self.toolbar.setObjectName(u'JRectifier')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('JRectifier', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip = None,
        whats_this='JRectifier',
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToRasterMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action
        
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Create action that will start plugin configuration
        self.action = QAction(
            QIcon(':/plugins/J_Rectifier/icon.png'),
            'J Rectifier', self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToRasterMenu('&J Rectifier', self.action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.iface.removePluginRasterMenu('&J Rectifier', self.action)
        self.iface.removeToolBarIcon(self.action)

           
    #JANEK=======================THE MOST IMPORTANT CLASS OF THE PLUGIN, contains GUI and functionality.========================
    class DisplayedWindow(QDialog):
        global jg_running
        point_plug_path = None # displayed in plugin canvas vector points layer
        point_qgis_path = None # displayed in qgis canvas vector points layer
        err_plug_path = None #displayes in plugin canvas vecrot line layer (corrections)
        err_qgis_path = None
        raster_path = None
        output_path = None
        spatial_ref = None
        
        def __init__(self):
            global point_plug_path, point_plug_path, raster_path, qgis_srs_epsg, err_plug_path, err_qgis_path, jg_running
            
            jg_running = 1 
            point_plug_path = None # displayed in plugin canvas vector points layer
            point_qgis_path = None # displayed in qgis canvas vector points layer
            raster_path = None
            qgis_srs_epsg = None
            
            #JANEK ==============GUI==============
            #JANEK ==============GUI Layouts==============
            #JANEK Main dialog
            self.window_plugin = QtGui.QDialog() # QtGui.QMainWindow()
            self.window_plugin.setWindowModality(QtCore.Qt.WindowModal) #JANEK Plugin window don't block QGIS window now, when plugin is running
            self.window_plugin.setWindowTitle('J Rectifier')
            self.window_plugin.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint ) #|Qt.WindowMaximizeButtonHint) #JANEK adding minimize and maximize buttons
            self.window_plugin.setContentsMargins(-18,-18,-18,-18) # MUST CHECK if it works fine on other operation systems
            self.window_plugin.setWindowIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/icon.png') )) #setting icon
            
            self.splitter = QtGui.QSplitter(Qt.Vertical) #SPLITTER ALLOWS TO change size widgets(layouts by dragging. 
            
            self.main_layout = QGridLayout(self.window_plugin) # Main window - devided bt splitter into 2 parts
            self.top_layout = QGridLayout(self.window_plugin)
            self.bottom_layout = QGridLayout(self.window_plugin)
            
            #JANEK PANEL 1 - the panel below map canvas with add raster button, zoom buttons and checkboxes
            self.panel1 = QGridLayout(self.window_plugin)
            self.panel1.setAlignment(Qt.AlignJustify)
            #INSIDE Panel 1
            self.zoom_layout = QGridLayout(self.window_plugin)
            self.zoom_layout.setAlignment(Qt.AlignCenter)
            self.checkbox_layout = QGridLayout(self.window_plugin)
            self.panel1.addLayout(self.zoom_layout, 0, 1)
            self.panel1.addLayout(self.checkbox_layout, 0, 2)
            
            #Janek Raster window #the very top of the window
            #self.window_frame = QtGui.QFrame(self.window_plugin)
            #self.window_frame.move(0, 0)
            self.frame_layout = QtGui.QGridLayout(self.window_plugin)
            self.canvas = QgsMapCanvas()
            self.frame_layout.addWidget(self.canvas)
            self.top_layout.addLayout(self.frame_layout, 0, 0, Qt.AlignCenter)
            
            #JANEK Table layout
            self.table_layout = QGridLayout(self.window_plugin)
            
            #Inside table layout || inside will be a table, and a column of buttons they will be added down below when we create them
            self.buttons_layout = QGridLayout(self.window_plugin)
            
            #JANEK Panel2 - layout at the very bottom of the window
            self.panel2 = QGridLayout(self.window_plugin)
            
            #Inside Panel2
            self.labels_layout = QVBoxLayout(self.window_plugin)
            self.labels_layout.setSpacing(1)
            self.labels_layout.addStretch()
            self.combobox_layout = QGridLayout(self.window_plugin)
            self.panel2.addLayout(self.labels_layout, 0 , 0, Qt.AlignCenter)
            self.panel2.addLayout(self.combobox_layout, 0 , 1, Qt.AlignCenter)    
            
            #JANEK =================GUI - BUTTONS=========================
            #JANEK read raster layer button
            self.btn_open_raster = QtGui.QToolButton(self.window_plugin)
            self.btn_open_raster.setToolTip("Load raster file\n[CTRL+R]")
            self.btn_open_raster.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/AddRasterLayer.png') ))
            self.btn_open_raster.setIconSize( QSize(30, 30) )
            self.btn_open_raster.clicked.connect(lambda: self.click_btn_open_raster())
            self.btn_open_raster.setShortcut('Ctrl+R')
            self.btn_open_raster.setStyleSheet('border: none;')
            self.panel1.addWidget(self.btn_open_raster, 0, 0, Qt.AlignVCenter)

            #JANEK execute button
            self.btn_exec = QtGui.QToolButton(self.window_plugin)
            self.btn_exec.setToolTip("Georeference it!")
            self.btn_exec.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/Play.png') ))
            self.btn_exec.setIconSize( QSize(50, 30) )
            self.btn_exec.clicked.connect(lambda: self.click_btn_exec())
            #self.btn_exec.setStyleSheet('border: none;')
            self.panel2.addWidget(self.btn_exec, 0, 3, Qt.AlignRight)

            #JANEK add point add point button
            self.btn_add_point = QtGui.QToolButton()
            self.btn_add_point.setCheckable(True) #JANEK the button stays checked when you ckick it
            self.btn_add_point.setToolTip("Add points\n[CTRL+W]")
            self.btn_add_point.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/Plus.png') ))
            self.btn_add_point.setIconSize( QSize(20, 20) )
            self.btn_add_point.clicked.connect(lambda: self.click_btn_add_point())
            self.btn_add_point.toggled.connect(lambda: self.toggle_btn_add_point())
            self.btn_add_point.setShortcut('Ctrl+W')
            self.btn_add_point.setStyleSheet('border: none;')
            self.buttons_layout.addWidget(self.btn_add_point, 0,0)

            #JANEK delete point button
            self.btn_del_point = QtGui.QToolButton(self.window_plugin)
            self.btn_del_point.setToolTip("Delete points\n[CTRL+D]")
            self.btn_del_point.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/X.png') ))
            self.btn_del_point.setIconSize( QSize(20, 20) )
            self.btn_del_point.clicked.connect(lambda: self.click_btn_del_point())
            self.btn_del_point.setShortcut('Ctrl+D')
            self.btn_del_point.setStyleSheet('border: none;')
            self.buttons_layout.addWidget(self.btn_del_point, 1,0)
            
            #JANEK edit point button
            self.btn_edit_point = QtGui.QToolButton(self.window_plugin)
            self.btn_edit_point.setCheckable(True) #JANEK the button stay checked when you ckick it
            self.btn_edit_point.setToolTip("Edit selected point\n[CTRL+E]")
            self.btn_edit_point.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/Edit.png') ))
            self.btn_edit_point.setIconSize( QSize(25, 25) )
            self.btn_edit_point.clicked.connect(lambda: self.click_btn_edit_point())
            self.btn_edit_point.toggled.connect(lambda: self.toggle_btn_edit_point())
            self.btn_edit_point.setShortcut('Ctrl+E')
            self.btn_edit_point.setStyleSheet('border: none;')
            self.buttons_layout.addWidget(self.btn_edit_point, 2,0)

           
           #JANEK type points button
            self.btn_type_points = QtGui.QToolButton(self.window_plugin)
            self.btn_type_points.move(715, 505)
            self.btn_type_points.setToolTip("Type points coordinates\n[CTRL+T]")
            self.btn_type_points.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/num_pad.png') ))
            self.btn_type_points.setIconSize( QSize(25, 25) )
            self.btn_type_points.clicked.connect(lambda: self.click_btn_type_points())
            self.btn_type_points.setShortcut('Ctrl+T')
            self.btn_type_points.setStyleSheet('border: none;')
            self.buttons_layout.addWidget(self.btn_type_points, 3,0)
            
            #JANEK save points button
            self.btn_save_points = QtGui.QToolButton(self.window_plugin)
            self.btn_save_points.move(715, 540)
            self.btn_save_points.setToolTip("Save points\n[CRTL+S]")
            self.btn_save_points.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/Save.png') ))
            self.btn_save_points.setIconSize( QSize(25, 25) )
            self.btn_save_points.clicked.connect(lambda: self.click_btn_save_points())
            self.btn_save_points.setShortcut('Ctrl+S')
            self.btn_save_points.setStyleSheet('border: none;')
            self.buttons_layout.addWidget(self.btn_save_points, 4,0)

            #JANEK read points button
            self.btn_read_points = QtGui.QToolButton(self.window_plugin)
            self.btn_read_points.move(715, 575)
            self.btn_read_points.setToolTip("Read points")
            self.btn_read_points.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/Open.png') ))
            self.btn_read_points.setIconSize( QSize(25, 25) )
            self.btn_read_points.clicked.connect(lambda: self.click_btn_read_points())
            self.btn_read_points.setStyleSheet('border: none;')
            self.buttons_layout.addWidget(self.btn_read_points, 5,0)
            
            #JANEK btn_zoom_all (Full Extent)
            self.btn_zoom_all = QtGui.QToolButton(self.window_plugin)
            self.btn_zoom_all.setToolTip("Zoom to full extent\n[CTRL+F]")
            self.btn_zoom_all.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/zoom_ex.png') ))
            self.btn_zoom_all.setIconSize( QSize(25, 25) )
            self.btn_zoom_all.clicked.connect(lambda: self.canvas.zoomToFullExtent())
            self.btn_zoom_all.setShortcut('Ctrl+F')
            self.btn_zoom_all.setStyleSheet('border: none;')
            self.zoom_layout.addWidget(self.btn_zoom_all, 0, 0, Qt.AlignCenter)

            #JANEK btn_zoom_selected
            self.btn_zoom_selected = QtGui.QToolButton(self.window_plugin)
            self.btn_zoom_selected.setToolTip("Zoom to selected point\n[CTRL+Z]")
            self.btn_zoom_selected.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/zoom_select.png') ))
            self.btn_zoom_selected.setIconSize( QSize(25, 25) )
            self.btn_zoom_selected.clicked.connect(lambda: click_btn_zoom_selected())
            self.btn_zoom_selected.setShortcut('Ctrl+Z')
            self.btn_zoom_selected.setStyleSheet('border: none;')
            self.zoom_layout.addWidget(self.btn_zoom_selected, 0, 1, Qt.AlignCenter)
            
            #JANEK btn_zoom_prev 
            self.btn_zoom_prev = QtGui.QToolButton(self.window_plugin)
            self.btn_zoom_prev.setToolTip("Zoom to previous extent")
            self.btn_zoom_prev.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/zoom_last.png') ))
            self.btn_zoom_prev.setIconSize( QSize(25, 25) )
            self.btn_zoom_prev.clicked.connect(lambda: self.canvas.zoomToPreviousExtent())
            self.btn_zoom_prev.setStyleSheet('border: none;')
            self.zoom_layout.addWidget(self.btn_zoom_prev, 0, 2, Qt.AlignCenter)
            
            #JANEK btn_zoom_next
            self.btn_zoom_next = QtGui.QToolButton(self.window_plugin)
            self.btn_zoom_next.setToolTip("Zoom to next extent")
            self.btn_zoom_next.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/zoom_next.png') ))
            self.btn_zoom_next.setIconSize( QSize(25, 25) )
            self.btn_zoom_next.clicked.connect(lambda: self.canvas.zoomToNextExtent())
            self.btn_zoom_next.setStyleSheet('border: none;')
            self.zoom_layout.addWidget(self.btn_zoom_next, 0, 3, Qt.AlignCenter)
            
            #JANEK btn_highlight
            self.btn_highlight = QtGui.QToolButton(self.window_plugin)
            self.btn_highlight.setToolTip("Highlight points\n[Ctrl+H]")
            self.btn_highlight.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/highlight.png') ))
            self.btn_highlight.setIconSize( QSize(25, 25) )
            self.btn_highlight.setShortcut('Ctrl+H')
            self.btn_highlight.clicked.connect(lambda: self.click_btn_highlight())
            self.btn_highlight.setStyleSheet('border: none;')
            self.zoom_layout.addWidget(self.btn_highlight, 0, 4, Qt.AlignCenter)
            self.highlight = False # used for highligting points
            
            #JANEK=============GUI - comboboxes
            #JANEK method combobox
            self.meth_combobox = QtGui.QComboBox(self.window_plugin)
            self.meth_combobox.resize(80, 20)
            self.meth_combobox.setToolTip("Choose georeferancing method")
            self.meth_combobox.addItems(['Helmert' , 'Polynomial 1', 'Polynomial 2', 'Polynomial 3', 'Spline (TPS)']) # 'Line'
            self.meth_combobox.currentIndexChanged.connect(lambda: self.table.refresh(self))
            self.combobox_layout.addWidget(self.meth_combobox, 1, 0, Qt.AlignCenter)

            
            #JANEK resampling combobox
            self.rsmp_combobox = QtGui.QComboBox(self.window_plugin)
            self.rsmp_combobox.resize(80, 20)
            self.rsmp_combobox.setToolTip("Choose resampling method")
            self.rsmp_combobox.addItems(['Nearest', 'Bilinear', 'Cubic', 'Cubic spline', 'Lanczos'] )
            self.combobox_layout.addWidget(self.rsmp_combobox, 1, 1, Qt.AlignCenter)

            
            #JANEK compression combobox
            self.comp_combobox = QtGui.QComboBox(self.window_plugin)
            self.comp_combobox.resize(80, 20)
            self.comp_combobox.setToolTip("Choose compression method")
            self.comp_combobox.addItems(['NONE', 'LZW', 'PACKBITS', 'DEFLATE'] )
            self.combobox_layout.addWidget(self.comp_combobox, 1, 2, Qt.AlignCenter)

            #JANEK==============OTHER GUI OBJECTS==============
            #JANEK GCP table
            self.table = QtGui.QTableWidget(self.window_plugin) #JANEK Assignin table to main window
            self.table.setColumnCount(8)
            headers = ['Accept','x','y','X','Y','d X', 'd Y','d XY']
            self.table.setHorizontalHeaderLabels(headers)
            self.table.setColumnWidth(0, 43)
            for i in range(4):
                self.table.setColumnWidth(i+1, 100)
            for i in [5,6,7]:
                self.table.setColumnWidth(i, 80)
            #self.table.setSortingEnabled(True)
            self.table.itemClicked.connect(lambda: accept_yes2no(self.table))
            self.table.itemDoubleClicked.connect(lambda: zoom_to_points(self.table.selectedItems()[0].row()+1))
            self.table_frame = QtGui.QGridLayout(self.window_plugin)# QtGui.QVBoxLayout(window2)
            self.table_frame.addWidget(self.table)
            self.table_layout.addLayout(self.table_frame, 0 ,0 )
            self.table_layout.addLayout(self.buttons_layout, 0, 1)
            self.buttons_layout.setAlignment( Qt.AlignHCenter | Qt.AlignTop )            
                                        
            #JANEK Zoom checkbox
            self.zoom_checkbox = QtGui.QCheckBox(self.window_plugin)
            self.zoom_checkbox.setChecked(True)
            self.zoom_checkbox.setText('auto zoom')
            self.checkbox_layout.addWidget(self.zoom_checkbox, 0, 0)#, Qt.AlignLeft)

            #JANEK show error checkbox
            self.err_checkbox = QtGui.QCheckBox(self.window_plugin)
            self.err_checkbox.setChecked(True)
            self.err_checkbox.setText('show errors on maps')
            self.err_checkbox.toggled.connect(lambda: self.toggled_err_checkbox())
            self.checkbox_layout.addWidget(self.err_checkbox, 1, 0)#, Qt.AlignLeft)

            #Janek Labels
            self.label_combobox = QtGui.QLabel(self.window_plugin)
            self.label_combobox.setText('Transformation:')
            self.combobox_layout.addWidget(self.label_combobox, 0, 0)

            
            self.label_combobox = QtGui.QLabel(self.window_plugin)
            self.label_combobox.setText('Resampling:')
            self.combobox_layout.addWidget(self.label_combobox, 0, 1)

            
            self.label_combobox = QtGui.QLabel(self.window_plugin)
            self.label_combobox.setText('Compression:')
            self.combobox_layout.addWidget(self.label_combobox, 0, 2)
            
            self.label_mXY = QtGui.QLabel(self.window_plugin)
            self.label_mXY.setText('m XY =')
            self.label_mXY.setMinimumWidth(150)
            self.labels_layout.addWidget(self.label_mXY)
            
            self.label_mX = QtGui.QLabel(self.window_plugin)
            self.label_mX.setText('m X =')
            self.label_mX.setMinimumWidth(150)
            self.labels_layout.addWidget(self.label_mX)

            
            self.label_mY = QtGui.QLabel(self.window_plugin)
            self.label_mY.setText('m Y =')
            self.label_mY.setMinimumWidth(150)
            self.labels_layout.addWidget(self.label_mY)

            
            self.label_epsg = QtGui.QLabel(self.window_plugin)
            self.label_epsg.setText('Destination EPSG: ')
            self.label_epsg.setMinimumWidth(150)
            self.labels_layout.addWidget(self.label_epsg)
            
            #JANEK ======= PUTTING GUI WHOLE TOGETHER
            self.top_layout.addLayout(self.panel1, 1, 0)
            self.bottom_layout.addLayout(self.table_layout, 0, 0)
            self.bottom_layout.addLayout(self.panel2, 1, 0)
            self.bottom_layout.setRowStretch(0, 1) #now the bottom layout doesnt change size when we resize window. only table changes it!!
            
            self.checkbox_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.labels_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.zoom_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.frame1 = QFrame() # we need to put layouts into frames so the QSplitter could work fine
            self.frame2 = QFrame()
            self.frame1.setLayout(self.top_layout)
            self.frame2.setLayout(self.bottom_layout)
            
            self.splitter.addWidget(self.frame1)
            self.splitter.addWidget(self.frame2)
            self.splitter.setCollapsible(0,False) # can't snap splitter to edge of window (prevent from hiding a qframe)
            self.splitter.setCollapsible(1,False)
            self.main_layout.addWidget(self.splitter, 0, 0)
            

            def closing_event(self):
                global point_plug_path, point_qgis_path, err_qgis_path, err_plug_path, jg_running
                
                #quit_msg = "Do you want to save points?"
                #reply = QtGui.QMessageBox.question(None, 'Quit Program', quit_msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
                #if reply == QtGui.QMessageBox.Yes:
                #else:
                #    event.ignore()
                
                #Chancing pointTool for normal one
                ar_cursor = QCursor()
                ar_cursor.setShape(Qt.ArrowCursor)
                qgis.utils.iface.mapCanvas().setCursor(ar_cursor)
                                
                #removing vector layers from canvas
                try:
                    if point_plug_path is not None or point_qgis_path is not None or err_qgis_path is not None or err_plug_path is not None:
                        layermap = QgsMapLayerRegistry.instance().mapLayers()
                        RemoveLayers = []
                        for name, layer in layermap.iteritems():
                            if layer.isValid():
                                if layer.source() == point_plug_path or layer.source() == point_qgis_path or layer.source() == err_qgis_path or layer.source() == err_plug_path:
                                    RemoveLayers.append(layer.id())
                        if len(RemoveLayers) > 0:
                            QgsMapLayerRegistry.instance().removeMapLayers( RemoveLayers )
                except NameError:
                    pass
                    
                jg_running = 0
                            
            self.window_plugin.closeEvent = closing_event
            
            #JANEK ======== TABLE.CONNECT FUNCTIONS    
            def accept_yes2no(QTableWidget): #JANEK - changing "ACCEPT" status of the row when its clicked - method assignet to table (1st column)
                #QTableWidget.selectedItem().setText('kurwa')
                global point_plug_path, point_qgis_path
                if QTableWidget.selectedItems()[0].column() == 0:
                    if QTableWidget.selectedItems()[0].text() == 'No':
                        QTableWidget.selectedItems()[0].setText('Yes')
                        QTableWidget.selectedItems()[0].setTextColor(Qt.green)
                        for i in range(1, 8):
                            QTableWidget.item(QTableWidget.selectedItems()[0].row(), i).setTextColor(Qt.black)
                    else:
                        QTableWidget.selectedItems()[0].setText('No')
                        QTableWidget.selectedItems()[0].setTextColor(Qt.red)
                        for i in range(1, 8):
                            QTableWidget.item(QTableWidget.selectedItems()[0].row(), i).setTextColor(Qt.gray)
                    #JANEKchange point layers display
                    if point_plug_path is not None and point_qgis_path is not None:
                        driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                        dataSource_p = driver.Open(point_plug_path,1)
                        dataSource_q = driver.Open(point_qgis_path,1)
                        vlayer_p = dataSource_p.GetLayer() #gettin inside layers
                        vlayer_q = dataSource_q.GetLayer()
                        for layer in [vlayer_p, vlayer_q]: #the same action for both disp layers
                            for feature in layer: #iterating features until delate
                                if feature.GetField('ID') == QTableWidget.selectedItems()[0].row() + 1:# find a feature with atribute ID the same as row of selected field in table
                                    new_acc = None
                                    if feature.GetField('ACCEPT') == 1: #changing ACCEPT value - Yes (1), No (0)
                                        new_acc = 0
                                    else:
                                        new_acc = 1
                                    feature.SetField('ACCEPT', new_acc)
                                    layer.SetFeature(feature) #assignin changed feature to layer
                                    feature.Destroy()
                            layer.ResetReading()
                        
                        dataSource_p = None #closing dataset - something like saving changes
                        dataSource_q = None
                        self.table.refresh(self) #refreshin table
                        '''self.canvas.refreshAllLayers()#refreshin canvases
                        self.canvas.refresh() 
                        qgis.utils.iface.mapCanvas().refreshAllLayers()
                        qgis.utils.iface.mapCanvas().refresh()'''
            
            def zoom_to_points(id): #JANEK good comments for workflow of this method you will find in class PointTool>>def canvasReleaseEvent(self, event):
                
                global point_plug_path, point_qgis_path
                if point_plug_path and point_qgis_path:
                    points_xyXY = [] #list of lists of points [x,y,X,Y]
                    accepted_indexes = [] #JANEK indexes of points accepted by user
                    for i in range(self.table.rowCount()): #JANEK - makin a list of accepted values in table
                        if self.table.item(i,0).text() == 'Yes' and self.table.item(i,1).text() != '-' and self.table.item(i,2).text() != '-' and self.table.item(i,3).text() != '-' and self.table.item(i,4).text() != '-':
                            points_xyXY.append([float(self.table.item(i,1).text()), float(self.table.item(i,2).text()), float(self.table.item(i,3).text()), float(self.table.item(i,4).text())])
                            accepted_indexes.append(i)
                    gcp_table = np.array(points_xyXY) #JANEK Converting list of lists into NUMPY table, for faster and easier calculations
                    ## Zooming on QGIS canvas
                    if self.table.item(id - 1,3).text() != '-' and self.table.item(id - 1,4).text() != '-':
                        x, y = float(self.table.item(id - 1,3).text()), float(self.table.item(id - 1,4).text())
                        qgis.utils.iface.mapCanvas().setCenter(QgsPoint(x, y))
                    elif len(gcp_table) > 1 and self.table.item(id - 1,3).text() == '-' and self.table.item(id - 1,4).text() == '-': 
                        x, y = float(self.table.item(id - 1,1).text()), float(self.table.item(id - 1,2).text())
                        helm_params = janek_transformations.JanekTransform().helm_trans(gcp_table)[6]
                        a, b, c, d = helm_params[0], helm_params[1], helm_params[2], helm_params[3]
                        predX = c + b*x - a*y
                        predY = d + a*x + b*y
                        qgis.utils.iface.mapCanvas().setCenter(QgsPoint(predX, predY)) 
                    # Zoming on PLUGIN canvas
                    if self.table.item(id - 1,1).text() != '-' and self.table.item(id - 1,2).text() != '-':
                        x, y = float(self.table.item(id - 1,1).text()), float(self.table.item(id - 1,2).text())
                        self.canvas.setCenter(QgsPoint(x, y))
                    elif len(gcp_table) > 1 and self.table.item(id - 1,1).text() == '-' and self.table.item(id - 1,2).text() == '-': 
                        X, Y = float(self.table.item(id - 1,3).text()), float(self.table.item(id - 1,4).text())
                        helm_params = janek_transformations.JanekTransform().helm_trans(gcp_table)[6]
                        a, b, c, d = helm_params[0], helm_params[1], helm_params[2], helm_params[3]
                        predy = (b*Y - d*b - a*X + a*c)/(a*a + b*b)
                        predx = (X + a*predy - c)/b
                        self.canvas.setCenter(QgsPoint(predx, predy))
                    
                    self.canvas.refresh()
                    qgis.utils.iface.mapCanvas().refresh()  
                                
            #JANEK==============REFRESHING TABLE and line vector layer 
            def refresh_table(self): #JANEK - calculate dx dy dxy errors for points depending on chosen transformation method
                global point_plug_path, point_plug_path, trans_results, gcp_table
                
                if self.meth_combobox.currentText() == 'Helmert':
                    self.rsmp_combobox.setEnabled(False)
                    self.comp_combobox.setEnabled(False)
                else:
                    self.rsmp_combobox.setEnabled(True)
                    self.comp_combobox.setEnabled(True)
                    

                points_xyXY = [] #list of lists of points [x,y,X,Y]
                accepted_indexes = [] #JANEK indexes of points accepted by user
                for i in range(self.table.rowCount()): #JANEK - makin a list of accepted values in table
                    if self.table.item(i,0).text() == 'Yes' and self.table.item(i,1).text() != '-' and self.table.item(i,2).text() != '-' and self.table.item(i,3).text() != '-' and self.table.item(i,4).text() != '-':
                        points_xyXY.append([float(self.table.item(i,1).text()), float(self.table.item(i,2).text()), float(self.table.item(i,3).text()), float(self.table.item(i,4).text())])
                        accepted_indexes.append(i)
                
                gcp_table = np.array(points_xyXY) #JANEK Converting list of lists into NUMPY table, for faster and easier calculations
                #JANEK --- HELMERT TRANSFORMATION
                if len(gcp_table) > 2 and self.meth_combobox.currentText() =='Helmert': # JANEk when  helmert - then must be minimum 2 points
                    trans_results = janek_transformations.JanekTransform().helm_trans(gcp_table) #JANEK as a variable you must give numpay array rather then list
                    helm_params = trans_results[6] # in file called janek_transformation is described what's happen here
                    a, b, c, d = helm_params[0], helm_params[1], helm_params[2], helm_params[3]
                    for i in range(self.table.rowCount()): 
                        self.table.item(i,5).setText('-')
                        self.table.item(i,6).setText('-')
                        self.table.item(i,7).setText('-')
#                        if i in accepted_indexes: #if the point is accepted - YES 1st column
#                            self.table.item(accepted_indexes[i],5).setText(str(trans_results[0][i]))
#                            self.table.item(accepted_indexes[i],6).setText(str(trans_results[1][i]))
#                            self.table.item(accepted_indexes[i],7).setText(str(trans_results[2][i]))
                        j = 0
                        for i in range(self.table.rowCount()):                            
                            if i in accepted_indexes: #if the point is accepted - YES in 1st column
                                self.table.item(i,5).setText(str(trans_results[0][j]))
                                self.table.item(i,6).setText(str(trans_results[1][j]))
                                self.table.item(i,7).setText(str(trans_results[2][j]))
                                j  += 1
                            elif self.table.item(i,1).text() != '-' and self.table.item(i,2).text() != '-' and self.table.item(i,3).text() != '-' and self.table.item(i,4).text() != '-' :
                                # 5 - calculate predicted X Y values to know where to zoom (HELMERT TRANSFORMATION FORMULA)
                                x, y = float(self.table.item(i,1).text()), float(self.table.item(i,2).text())
                                predX = c + b*x - a*y
                                predY = d + a*x + b*y
                                VX = predX - float(self.table.item(i,3).text()) 
                                VY = predY - float(self.table.item(i,4).text())
                                self.table.item(i, 5).setText(str(VX))
                                self.table.item(i, 6).setText(str(VY))
                                self.table.item(i, 7).setText(str(math.sqrt(VX*VX + VY*VY))) # V XY
                                
                    self.label_mXY.setText('m XY = ' + str(trans_results[3]))
                    self.label_mX.setText('m X = ' + str(trans_results[4]))
                    self.label_mY.setText('m Y = ' + str(trans_results[5]))
    
                # JANEK --- POLYNOMIAL TRANSFORMATIONS    
                elif (len(gcp_table) > 3 and self.meth_combobox.currentText() =='Polynomial 1') or (len(gcp_table) > 6 and self.meth_combobox.currentText() =='Polynomial 2') or (len(gcp_table) > 9 and self.meth_combobox.currentText() =='Polynomial 3'):
                    if self.meth_combobox.currentText() =='Polynomial 1': #choosing method among polynomials
                        order_num = 1
                    elif self.meth_combobox.currentText() =='Polynomial 2':
                        order_num = 2
                    if self.meth_combobox.currentText() =='Polynomial 3':
                        order_num = 3
                    trans_results = janek_transformations.JanekTransform().polynomial(order_num, gcp_table, 0, 1, 2, 3) # exec the function from other file that calculates errors
                    
                    for i in range(self.table.rowCount()): 
                        self.table.item(i,5).setText('-')
                        self.table.item(i,6).setText('-')
                        self.table.item(i,7).setText('-')
                    
                    j = 0
                    for i in range(self.table.rowCount()):                            
                        if i in accepted_indexes: #if the point is accepted - YES in 1st column
                            self.table.item(i,5).setText(str(-trans_results[0][j]))
                            self.table.item(i,6).setText(str(-trans_results[1][j]))
                            self.table.item(i,7).setText(str(trans_results[2][j]))
                            j  += 1
                        elif self.table.item(i,1).text() != '-' and self.table.item(i,2).text() != '-' and self.table.item(i,3).text() != '-' and self.table.item(i,4).text() != '-' :
                            X, Y = float(self.table.item(i,3).text()), float(self.table.item(i,4).text())
                            x, y = float(self.table.item(i,1).text()), float(self.table.item(i,2).text())
                            if order_num == 1:
                                a0, a1, a2 = trans_results[6]
                                b0, b1, b2 = trans_results[7]
                                predX = a0 + a1*x + a2*y
                                predY = b0 + b1*x + b2*y
                            elif order_num == 2:
                                a0, a1, a2, a3, a4, a5 = trans_results[6]
                                b0, b1, b2, b3, b4, b5 = trans_results[7]
                                predX = a0 + a1*x + a2*y + a3*x*y + a4*x*x + a5*y*y
                                predY = b0 + b1*x + b2*y + b3*x*y + b4*x*x + b5*y*y
                            if order_num == 3:
                                a0, a1, a2, a3, a4, a5, a6, a7, a8, a9 = trans_results[6]
                                b0, b1, b2, b3, b4, b5, b6, b7, b8, b9 = trans_results[7]
                                predX = a0 + a1*x + a2*y + a3*x*y + a4*x*x + a5*y*y + a6*x*x*x + a7*x*x*y + a8*x*y*y + a9*y*y*y
                                predY = b0 + b1*x + b2*y + b3*x*y + b4*x*x + b5*y*y + b6*x*x*x + b7*x*x*y + b8*x*y*y + b9*y*y*y
                                
                            VX = predX - X
                            VY = predY - Y
                            self.table.item(i, 5).setText(str(VX))
                            self.table.item(i, 6).setText(str(VY))
                            self.table.item(i, 7).setText(str(math.sqrt(VX*VX + VY*VY)))
                                
                            
                    
                    self.label_mXY.setText('m XY = ' + str(trans_results[3]))
                    self.label_mX.setText('m X = ' + str(trans_results[4]))
                    self.label_mY.setText('m Y = ' + str(trans_results[5]))
                        
                else:
                    for i in range(self.table.rowCount()): 
                        self.table.item(i,5).setText('-')
                        self.table.item(i,6).setText('-')
                        self.table.item(i,7).setText('-') 
                        self.label_mXY.setText('m XY =')
                        self.label_mX.setText('m X =')
                        self.label_mY.setText('m Y =')
                        
                update_lines() #update vector layers with errors
                self.canvas.refreshAllLayers()#refreshin canvases
                self.canvas.refresh() 
                qgis.utils.iface.mapCanvas().refreshAllLayers()
                qgis.utils.iface.mapCanvas().refresh()
            
            self.table.refresh = refresh_table #JANEK adding method to the table class so i can use it later in pointools and other functions/classes
            
            def update_lines(): #everytime the table changes it delate all lines and add them once again (USED LATER IN self.table.refresh
                global err_qgis_path, err_plug_path, trans_results, gcp_table
                
                #if err_qgis_path is not None and err_qgis_path is not None:
                if self.table.rowCount() > 0:
                    driver = ogr.GetDriverByName('ESRI shapefile')
                    for path in [err_qgis_path, err_plug_path]: 
                        dataSource = driver.Open(path, 1)
                        layer = dataSource.GetLayer()
                        for feature in layer:
                            layer.DeleteFeature(feature.GetFID())
                        feature = None
                        featureDefn = layer.GetLayerDefn()
                        if path == err_qgis_path: #JANEK UPDATING LAYER IN QGIS CANVAS
                            for row in range(self.table.rowCount()):
                                if self.table.item(row,7).text() !='-': # if row is empty and has computer errors
                                    line = ogr.Geometry(ogr.wkbLineString)
                                    line.AddPoint(float(self.table.item(row,3).text()), float(self.table.item(row,4).text())) # X, Y from table
                                    line.AddPoint(float(self.table.item(row,3).text())+ float(self.table.item(row,5).text()) , float(self.table.item(row,4).text()) + float(self.table.item(row,6).text())) # X + VX, Y + VY
                                    feature = ogr.Feature(featureDefn)
                                    feature.SetGeometry(line)
                                    if self.err_checkbox.isChecked():
                                        feature.SetField('SHOW', 1)
                                    else:
                                        feature.SetField('SHOW', 0)
                                    layer.CreateFeature(feature)
                                    feature = None
                        else: #JANEK UPDATING LAYER IN PLUGIn CANVAS
                            if self.meth_combobox.currentText() == 'Helmert' and len(gcp_table) > 2:
                                helm_params = trans_results[6] # in file called janek_transformation is described what's happen here
                                a, b, c, d = helm_params[0], helm_params[1], helm_params[2], helm_params[3]
                                
                                for row in range(self.table.rowCount()): #JANEK UPDATING LAYER IN QGIS CANVAS - depends on chosen transformation method
                                    if self.table.item(row,7).text() !='-':
                                        x, y = float(self.table.item(row,1).text()), float(self.table.item(row,2).text()) ##Getting line points coordinates based on helmert transform
                                        X, Y = float(self.table.item(row,3).text()), float(self.table.item(row,4).text())
                                        predy = (b*Y - d*b - a*X + a*c)/(a*a + b*b)
                                        predx = (X + a*predy - c)/b
                                        line = ogr.Geometry(ogr.wkbLineString)
                                        line.AddPoint(x, y) # x, y from table
                                        line.AddPoint(predx, predy) # predicted x y from helmert
                                        feature = ogr.Feature(featureDefn)
                                        feature.SetGeometry(line)
                                        if self.err_checkbox.isChecked():
                                            feature.SetField('SHOW', 1)
                                        else:
                                            feature.SetField('SHOW', 0)
                                        layer.CreateFeature(feature)
                                        feature = None
                            
                            elif (len(gcp_table) > 3 and self.meth_combobox.currentText() =='Polynomial 1') or (len(gcp_table) > 6 and self.meth_combobox.currentText() =='Polynomial 2') or (len(gcp_table) > 9 and self.meth_combobox.currentText() =='Polynomial 3'):
                                if self.meth_combobox.currentText() =='Polynomial 1': #choosing method among polynomials
                                    order_num = 1
                                elif self.meth_combobox.currentText() =='Polynomial 2':
                                    order_num = 2
                                if self.meth_combobox.currentText() =='Polynomial 3':
                                    order_num = 3
                                trans_results = janek_transformations.JanekTransform().polynomial(order_num, gcp_table, 2, 3, 0, 1) # exec the function from other file that calculates errors
                                
                                for row in range(self.table.rowCount()): #JANEK UPDATING LAYER IN QGIS CANVAS - depends on chosen transformation method
                                    if self.table.item(row,7).text() !='-':
                                        x, y = float(self.table.item(row,1).text()), float(self.table.item(row,2).text()) ##Getting line points coordinates based on helmert transform
                                        X, Y = float(self.table.item(row,3).text()), float(self.table.item(row,4).text())
                                        if order_num == 1:
                                            a0, a1, a2 = trans_results[6]
                                            b0, b1, b2 = trans_results[7]
                                            predx = a0 + a1*X + a2*Y
                                            predy = b0 + b1*X + b2*Y
                                        elif order_num == 2:
                                            a0, a1, a2, a3, a4, a5 = trans_results[6]
                                            b0, b1, b2, b3, b4, b5 = trans_results[7]
                                            predx = a0 + a1*X + a2*Y + a3*X*Y + a4*X*X + a5*Y*Y
                                            predy = b0 + b1*X + b2*Y + b3*X*Y + b4*X*X + b5*Y*Y
                                        if order_num == 3:
                                            a0, a1, a2, a3, a4, a5, a6, a7, a8, a9 = trans_results[6]
                                            b0, b1, b2, b3, b4, b5, b6, b7, b8, b9 = trans_results[7]
                                            predx = a0 + a1*X + a2*Y + a3*X*Y + a4*X*X + a5*Y*Y + a6*X*X*X + a7*X*X*Y + a8*X*Y*Y + a9*Y*Y*Y
                                            predy = b0 + b1*X + b2*Y + b3*X*Y + b4*X*X + b5*Y*Y + b6*X*X*X + b7*X*X*Y + b8*X*Y*Y + b9*Y*Y*Y
                                        
                                        line = ogr.Geometry(ogr.wkbLineString)
                                        line.AddPoint(x, y) # x, y from table
                                        line.AddPoint(predx, predy) # predicted x y from polynomial
                                        feature = ogr.Feature(featureDefn)
                                        feature.SetGeometry(line)
                                        if self.err_checkbox.isChecked():
                                            feature.SetField('SHOW', 1)
                                        else:
                                            feature.SetField('SHOW', 0)
                                        layer.CreateFeature(feature)
                                        feature = None
                        dataSource = None

            def click_btn_zoom_selected(): #it should be below with all methods for buttons, but then it couldnt use zoom to points method ;-/. So its here
                try:
                    zoom_to_points(self.table.selectedItems()[-1].row()+1)
                except IndexError:
                    pass
             
#JANEK==============BUTTON FUNCTIONS====================
        def click_btn_open_raster(self): 
            global point_plug_path, point_qgis_path, raster_path, qgis_srs_epsg, plug_srs_epsg, err_qgis_path, err_plug_path, lyr_plug
            
            self.btn_add_point.setChecked(0) #ckicking out buttons
            self.btn_edit_point.setChecked(0)
            self.btn_highlight.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/highlight.png') )) #changing icon of the highlight button
            self.highlight = False # refreshing global variable used for changing layers styles
            
            #Settin Cursor and Point Tool for canvases (in case if they still remember old from adding or editing points
            ar_cursor = QCursor()
            ar_cursor.setShape(Qt.ArrowCursor)
            self.canvas.setCursor(ar_cursor)
            qgis.utils.iface.mapCanvas().setCursor(ar_cursor)
            
            tool2 = self.PointTool2(self.canvas, self.table)
            tool_qgs2 = self.PointTool2_MainQgisCanvas(qgis.utils.iface.mapCanvas(), self.table)
            self.canvas.setMapTool(tool2)
            qgis.utils.iface.mapCanvas().setMapTool(tool_qgs2)
            
            #checking if EPSG for QGIS map Canvas is selected - that's required
            if qgis.utils.iface.mapCanvas().mapRenderer().destinationCrs().authid()[5:] == '':
                QMessageBox.information(None, "Coordinate Reference System error", "Choose CRS for QGIS canvas.\nDo not change CRS during adding poits\nChosen CRS will be destination CRS of your georeferenced image.")
            else:
                #removing old vect layer from registry and to canvas
                if point_plug_path != None and point_qgis_path != None and err_qgis_path != None:
                    #point_plug_path = point_plug_path_old
                    #point_qgis_path = point_qgis_path_old                
                    for layer in QgsMapLayerRegistry.instance().mapLayersByName('J Rectifier: points'):
                        if layer.source() == point_qgis_path:
                            QgsMapLayerRegistry.instance().removeMapLayer(layer)
                    for layer in QgsMapLayerRegistry.instance().mapLayersByName('J Rectifier: errors'):
                        if  layer.source() == err_qgis_path:
                            QgsMapLayerRegistry.instance().removeMapLayer(layer)
                    
                point_plug_path = None
                point_qgis_path = None
                err_qgis_path = None
                err_qgis_path = None
               
                # JANEK ASK ABOUT SAVIG POINTS
                if self.table.rowCount() > 0: #if there are any points
                    save_raster_dial = QDialog()
                    save_raster_dial.setMinimumWidth(100)
                    save_raster_dial.setGeometry(400, 400, 100, 60)
                    save_raster_dial.setWindowFlags(Qt.WindowStaysOnTopHint)
                    save_raster_dial.setWindowTitle('Save points')
                    save_raster_dial.setFixedSize(470, 100) #block size

                    #JANEK=========Labels
                    msg_label = QLabel(save_raster_dial)
                    msg_label.move(100, 20)
                    msg_label.setText('Do you want to save points?')
      
                    #JANEK=========Buttons and it's functions
                    yes_button = QPushButton(save_raster_dial)
                    yes_button.setText('Yes')
                    yes_button.move(290,65)
                    yes_button.clicked.connect(lambda: click_yes_button())
                    
                    no_button = QPushButton(save_raster_dial)
                    no_button.setText('No')
                    no_button.move(370,65)
                    no_button.clicked.connect(lambda: save_raster_dial.close())

                    def click_yes_button():
                        save_raster_dial.close()
                        self.click_btn_save_points()
                        #save_raster_dial.close()
                        
                    save_raster_dial.exec_()
                        
                    
                #JANEK Clearing the table
                for i in reversed(range(self.table.rowCount())):
                    self.table.removeRow(i)
                               
                #Setting raster in plugin canvas
                if raster_path != None:
                    raster_path = QFileDialog.getOpenFileName(None,"Select raster file",raster_path[:-len(raster_path.split('/')[-1])],"").encode('utf8') #Getting the file (from raster catalog)
                    #raster_path = raster_path.encode('utf8') #encoding to avoid problemd with non-english letters
                    if raster_path != '':
                        path_memory = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'memory\\path_memory.txt'), 'w') #wrighting a new path for future
                        path_memory.write(raster_path)
                        path_memory.close()
                else:
                    try:
                        path_memory = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'memory\\path_memory.txt'), 'r') #opening textfile with path
                        open_path = path_memory.readline()
                        path_memory.close()
                        raster_path = QFileDialog.getOpenFileName(None,"Select points file", open_path, "").encode('utf8') #wrighting a new path for future
                        if raster_path != '':
                            path_memory = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'memory\\path_memory.txt'), 'w')
                            path_memory.write(raster_path)
                            path_memory.close()
                    except:
                        raster_path = QFileDialog.getOpenFileName(self.window_plugin,"Select raster file","","").encode('utf8') #GLOBAL
                        if raster_path != '':
                            path_memory = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'memory\\path_memory.txt'), 'w') #wrighting a new path for future
                            path_memory.write(raster_path)
                            path_memory.close()
                
                if raster_path != '': #if somebody didnt abandoned opening file
                
                    self.window_plugin.setWindowTitle('J Rectifier | '+ raster_path.split('/')[-1])
                                        
                    lyr = QgsRasterLayer(raster_path.decode('utf8'), 'JANEK Georeference raster')
                    
                    #Janek check if raster has CRS assigned
                    raster_gdal = gdal.Open(raster_path, 0)
                    if raster_gdal.GetProjection() =='':
                        raster_gdal = None # closing GDAL
                        
                        crs = lyr.crs()
                        crs.createFromId(4326)
                        lyr.setCrs(crs)# DOESNT WORK /// this is done to avoid prompt (useless for plugin purposes) CRS dialog, which is displayed when we try to load layer without CRS (f.e JPG file)
                        self.canvas.mapRenderer().setDestinationCrs(crs)
                    else:
                        raster_gdal = None # closing GDAL
                        QMessageBox.warning(None, "Input warning", "The file already has got Coordinate Reference System. \nThe output file will NOT be correct.")
                    
                    lyr_reg = QgsMapLayerRegistry
                    QgsMapLayerRegistry.instance().addMapLayer(lyr, False) #JANEK False - so it doesn't appear in main QGIS window canvas
                    canvas_lyr = QgsMapCanvasLayer(lyr)
                    self.canvas.setLayerSet([canvas_lyr])
                    self.canvas.zoomToFullExtent()
                    self.canvas.enableAntiAliasing(True) #JANEK reportedly it causes better rendering
                    
                    #Creating vector layers displayed on plugin canvas and QGIS canvas (GDAL)
                    #JANEK creating layers and prj files
                    current_time = datetime.datetime.now().strftime('%Y%m%d%H%M%S') #JANEK that is the string with the current time for naming temp layers
                    temp_path = os.path.join(os.path.dirname(__file__),'temp')
                    
                    point_plug_path = os.path.join(temp_path,'pts_plug' + current_time +'.shp') #makin file paths in temporary catalog
                    point_qgis_path = os.path.join(temp_path,'pts_qgis' + current_time +'.shp')
                    err_plug_path = os.path.join(temp_path,'err_plug' + current_time +'.shp')
                    err_qgis_path = os.path.join(temp_path,'err_qgis' + current_time +'.shp')
                    point_plug_prj_path = os.path.join(temp_path,'pts_plug' + current_time +'.prj')
                    point_qgis_prj_path = os.path.join(temp_path,'pts_qgis' + current_time +'.prj')
                    err_plug_prj_path = os.path.join(temp_path,'err_plug' + current_time +'.prj')
                    err_qgis_prj_path = os.path.join(temp_path,'err_qgis' + current_time +'.prj')
                    
                    

                    driver = ogr.GetDriverByName('ESRI shapefile')
                    qgis_srs_epsg = qgis.utils.iface.mapCanvas().mapRenderer().destinationCrs().authid()[5:]#JanekEPSG of srs of current qgis canvas
                    plug_srs_epsg = self.canvas.mapRenderer().destinationCrs().authid()[5:] #JANEk EPGS of srs of plugin canvas
                    self.label_epsg.setText('Destination EPSG: ' + qgis_srs_epsg) #setting the text of label with destination epsg
                                    
                    spatialRef_qgis = osr.SpatialReference() #object for spatial ref
                    spatialRef_plug = osr.SpatialReference()
                    spatialRef_qgis.ImportFromEPSG(int(qgis_srs_epsg)) #assignin by EPSGs taken from canvases
                    spatialRef_plug.ImportFromEPSG(int(plug_srs_epsg))
                    spatialRef_qgis.MorphToESRI() #convert to esri format
                    spatialRef_plug.MorphToESRI()
                    prj_file_plug = open(point_plug_prj_path,'w') #create .prj text file
                    prj_file_qgis = open(point_qgis_prj_path,'w')
                    prj_err_file_plug = open(err_plug_prj_path,'w')
                    prj_err_file_qgis = open(err_qgis_prj_path,'w')
                    prj_file_plug.write(spatialRef_plug.ExportToWkt())# fillin in .prj file
                    prj_file_qgis.write(spatialRef_qgis.ExportToWkt())
                    prj_err_file_plug.write(spatialRef_plug.ExportToWkt())
                    prj_err_file_qgis.write(spatialRef_qgis.ExportToWkt())
                    prj_file_plug.close()#closing/saving
                    prj_file_qgis.close()
                    prj_err_file_plug.close()
                    prj_err_file_qgis.close()
                    
                    dataSource_qgis = driver.CreateDataSource(point_qgis_path) #create empty point - shapefiles
                    dataSource_plug = driver.CreateDataSource(point_plug_path)
                    dataSource_err_q = driver.CreateDataSource(err_plug_path)
                    dataSource_err_p = driver.CreateDataSource(err_qgis_path)
                    
                    qgis_lr = dataSource_qgis.CreateLayer('qgis_disp_points', geom_type=ogr.wkbPoint) #creating empty layers
                    plug_lr = dataSource_plug.CreateLayer('plug_disp_points', geom_type=ogr.wkbPoint)
                    err_q_lr = dataSource_err_q.CreateLayer('qgis_err_lines', geom_type=ogr.wkbLineString)
                    err_p_lr = dataSource_err_p.CreateLayer('plug_err_lines', geom_type=ogr.wkbLineString)
                    
                    field_id = ogr.FieldDefn('ID', ogr.OFTInteger)# POINT LAYERS create id/accept fields inside layers
                    field_accept = ogr.FieldDefn('ACCEPT', ogr.OFTInteger)
                    plug_lr.CreateField(field_id) #assignin fields to layers
                    plug_lr.CreateField(field_accept)
                    qgis_lr.CreateField(field_id)
                    qgis_lr.CreateField(field_accept)
                    
                    field_show = ogr.FieldDefn('SHOW', ogr.OFTInteger)# LINE layers create 'show' field
                    err_q_lr.CreateField(field_show)
                    err_p_lr.CreateField(field_show)
                    
                    
                    dataSource_qgis = None #close data sources not to couse errors
                    dataSource_plug = None
                    dataSource_err_q = None
                    dataSource_err_p = None
                    
                    ###########ADDING RASTER and VECTOR LAYERS TO CANVASES
                    
                    lyr_plug = QgsVectorLayer(point_plug_path,'JANEK Points Plugin canvas', 'ogr')
                    lyr_err_plug = QgsVectorLayer(err_plug_path,'JANEK errors', 'ogr')
                    #lyr_qgis = QgsVectorLayer(point_qgis_path,'JANEK Points QGIS canvas', 'ogr') 
                    QgsMapLayerRegistry.instance().addMapLayer(lyr_plug, False)#JANEK False - so it doesn't appear in main QGIS window canvas
                    QgsMapLayerRegistry.instance().addMapLayer(lyr_err_plug, False)
                    #QgsMapLayerRegistry.instance().addMapLayer(lyr_qgis, False)
                    canvas_lyr_plug = QgsMapCanvasLayer(lyr_plug)
                    canvas_lyr_err_plug = QgsMapCanvasLayer(lyr_err_plug)
                    #canvas_lyr_qgis = QgsMapCanvasLayer(lyr_qgis)
                    #qgis.utils.iface.addVectorLayer(lyr_qgis)
                    qgis.utils.iface.addVectorLayer(err_qgis_path, 'J Rectifier: errors', 'ogr')
                    qgis.utils.iface.addVectorLayer(point_qgis_path, 'J Rectifier: points', 'ogr')
                    self.canvas.setLayerSet([canvas_lyr_plug, canvas_lyr_err_plug, canvas_lyr])
                    self.canvas.enableAntiAliasing(True) #JANEK reportedly it causes better rendering

                    #chancing display style of vect layers
                    plug_style_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),'styles/plug_canv_style.qml'))
                    qgis_style_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),'styles/qgis_canv_style.qml'))
                    err_style_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),'styles/err_canv_style.qml'))
                    lyr_plug.loadNamedStyle(plug_style_path) # changing layer style in plugin canvas
                    lyr_plug.triggerRepaint() #reloading/refteshing
                    lyr_err_plug.loadNamedStyle(err_style_path)
                    lyr_err_plug.triggerRepaint()             
                    
                    layers = qgis.utils.iface.legendInterface().layers()# changing layer style in qgis canvas
                    for layer in layers:
                        if layer.source() == point_qgis_path:
                            layer.loadNamedStyle(qgis_style_path)
                            layer.triggerRepaint()
                        elif layer.source() == err_qgis_path:
                            layer.loadNamedStyle(err_style_path)
                            layer.triggerRepaint()
                     
                    #JANEK=========== IMPORT POINTS - if in the same catalog exist '.point' file with the same name f.e. [Raster.jpg] and [Raster.jpg.points]
                    points_path = raster_path + '.points'
                    if os.path.exists(points_path): # loaded [Raster.jpg] -> IF [Raster.jpg.points] exist...
                    
                        points_arr = np.loadtxt(points_path, skiprows=1, delimiter=',') #creating numpy array with points from file [X,Y,x,y,ACCEPT(1 or 0)], empty values are '-99999999999999'
                        #added_row = 0
                        for i in range(len(points_arr)): 
                            #added_row += i
                            self.table.insertRow(i)
                            
                            for j in [[1,2], [2,3], [3,0], [4,1]]: #because table is accept,x,y,X,Y and file is X,Y,x,y,accept (because that is .points format from georeferencer ;-/)
                                if points_arr[i, j[1]] != -9999999999:
                                    self.table.setItem(i, j[0], QtGui.QTableWidgetItem(''))
                                    self.table.item(i, j[0]).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                                    self.table.item(i, j[0]).setText(str(points_arr[i, j[1]]))
                                else:
                                    self.table.setItem(i, j[0], QtGui.QTableWidgetItem(''))
                                    self.table.item(i, j[0]).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                                    self.table.item(i, j[0]).setText('-')
                                
                            for k in [0, 5, 6, 7]:  # JANEK set columns accept/dx/dy/dxy gray and non-editable
                                self.table.setItem(i, k, QtGui.QTableWidgetItem(''))
                                self.table.item(i,k).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                                self.table.item(i,k).setBackgroundColor(Qt.lightGray)
                                if k !=0:
                                    self.table.item(i, k).setText('-') # Fill boxes dx dy dxy
                            if points_arr[i, 4] == 1:
                                self.table.item(i, 0).setText('Yes')
                                self.table.item(i,0).setTextColor(Qt.green) #Janek ACCEPT ROW
                                self.table.item(i,0).setTextAlignment(Qt.AlignCenter) #Janek ACCEPT ROW
                            else:
                                self.table.item(i, 0).setText('No')
                                self.table.item(i,0).setTextColor(Qt.red) #Janek ACCEPT ROW
                                self.table.item(i,0).setTextAlignment(Qt.AlignCenter) #Janek ACCEPT ROW
                                
                            #added_row += i
                            
                        #UPDATING vect layers (deleta all points and read them once again from table)
                        driver = ogr.GetDriverByName('ESRI shapefile')
                        for lr_path in [point_plug_path,point_qgis_path]:
                            dataSource = driver.Open(lr_path, 1) #open layer 1- edition mode
                            layer = dataSource.GetLayer()
                            for feature in layer: #delating all points
                                layer.DeleteFeature(feature.GetFID())
                            feature = None
                            
                            featureDefn = layer.GetLayerDefn()                    
                            if lr_path == point_plug_path:
                                col_x, col_y = 1, 2 # number of columns in self.table
                            else:
                                col_x, col_y = 3, 4
                            for i in range(self.table.rowCount()): #creating new points and adding them to layer
                                if self.table.item(i, col_x).text() != '-' and self.table.item(i, col_y).text() != '-':
                                    feature = ogr.Feature(featureDefn)
                                    new_point = ogr.Geometry(ogr.wkbPoint)
                                    x = float(self.table.item(i, col_x).text())
                                    y = float(self.table.item(i, col_y).text())
                                    new_point.AddPoint(x, y)
                                    feature.SetGeometry(new_point)
                                    feature.SetField('ID', i + 1)
                                    if self.table.item(i, 0).text() == 'Yes':
                                        feature.SetField('ACCEPT', 1)
                                    else:
                                        feature.SetField('ACCEPT', 0)
                                    layer.CreateFeature(feature)
                                    
                            feature = None
                            dataSource = None
                            
                        self.table.refresh(self)
                     
                    #REMOVING existing old vector layers files, if it can not delete because the file is open somewhere - it handles PASS
                    for file in os.listdir(temp_path): 
                        try:
                            if os.path.join(temp_path, file)[:-3] not in [point_plug_path[:-3], err_qgis_path[:-3], point_qgis_path[:-3], err_plug_path[:-3]]:
                                os.remove(os.remove(os.path.join(temp_path, file)))
                        except Exception:
                            pass
                    
        def click_btn_exec(self):
            global raster_path, qgis_srs_epsg, plug_srs_epsg, qgis_srs_epsg
            
            if raster_path is not None:    
                points_xyXY = [] #list of lists of points [x,y,X,Y]
                #accepted_indexes = [] #JANEK indexes of points accepted by user
                for i in range(self.table.rowCount()): #JANEK - makin a list of accepted values in table #WARNING - values goes as a STR not converted to FLOAT
                    if self.table.item(i,0).text() == 'Yes' and self.table.item(i,1).text() != '-' and self.table.item(i,2).text() != '-' and self.table.item(i,3).text() != '-' and self.table.item(i,4).text() != '-':
                        points_xyXY.append([self.table.item(i,1).text(), self.table.item(i,2).text(), self.table.item(i,3).text(), self.table.item(i,4).text()])
                                
                gcp_txt = ''
                for i in range(len(points_xyXY)):
                    gcp_txt += '-gcp ' + points_xyXY[i][0] + ' ' + str(-float(points_xyXY[i][1])) + ' ' + points_xyXY[i][2] + ' ' + points_xyXY[i][3] + ' ' #I dont know why but it works fin e when y (only y not Y) is opposite to the value in the table
                    
                #temp_rast_path = os.path.join(tempfile.mkdtemp(prefix='tmp'), raster_path.split('/')[-1])
                
                meth_dic = {'Polynomial 1': 'order 1', 'Polynomial 2': 'order 2', 'Polynomial 3': 'order 3','Spline (TPS)': 'tps', 'Helmert': 'helmert', 'Line': 'line'}
                min_points_dic = {'order 1': 3, 'order 2': 6, 'order 3': 9, 'tps': 3, 'helmert': 2, 'line': 3}
                rsmp_dic = {'Nearest': 'near', 'Bilinear': 'bilinear', 'Cubic': 'cubic', 'Cubic spline': 'cubicspline', 'Lanczos' : 'lanczos'} 
                
                tr_method = meth_dic[self.meth_combobox.currentText()] # transformatiom method txt (from COMBOBOX)
                min_points = min_points_dic[tr_method]
                
                rs_method = rsmp_dic[self.rsmp_combobox.currentText()] #resampling method txt
                cp_method = self.comp_combobox.currentText() # compresiom meth txt
                
                if len(points_xyXY) >= min_points:
                    temp_rast_path = os.path.join(tempfile.gettempdir(), raster_path.split('/')[-1])
                    
                    exec_dial = QDialog()
                    exec_dial.setGeometry(400, 400, 300, 300)
                    exec_dial.setFixedSize(250,270) #block size
                    exec_dial.setWindowFlags(Qt.WindowStaysOnTopHint)
                    exec_dial.setWindowTitle('Rectify summary')
                    exec_dial.setWindowIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/icon.png') )) #setting icon

                    

                    #JANEK=========Labels
                    msg_label = QTextBrowser(exec_dial)
                    msg_label.setFixedSize(240,210)
                    msg_label.move(5,5)
                    
                    #JANEK=========Buttons and it's functions
                    ok_button = QPushButton(exec_dial)
                    ok_button.setText('OK')
                    ok_button.move(70,240)
                    
                    cancel_button = QPushButton(exec_dial)
                    cancel_button.setText('Cancel')
                    cancel_button.move(160,240)
                    cancel_button.clicked.connect(lambda: exec_dial.close())
                    
                    pdf_checkbox = QCheckBox(exec_dial)
                    pdf_checkbox.setText('create PDF raport')
                    pdf_checkbox.move(5,215)
                    
                    def make_pdf_rap(outfile):
                        global raster_path, temporary_html_path
                        
                        #Removing files created during making previous pdf raport
                        for file in os.listdir(os.path.join(os.path.dirname(__file__),'print_template/')):
                            if file.endswith("template.htm") or file.endswith("JG_logo.png") :
                                pass
                            else:
                                os.remove(os.path.join(os.path.dirname(__file__),'print_template/',file))                                                
                        
                        #paths
                        pdf_path = outfile[:-len(outfile.split('/')[-1].split('.')[-1])] + '_raport.pdf' 
                        pdf_template_path = os.path.join(os.path.dirname(__file__),'print_template/template.htm')
                        temporary_html_path = os.path.join(os.path.dirname(__file__),'print_template/template' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')+ '.htm')# F.E ...JanekGeoreferencer/print_template/template1701011200.htm'
                        #raster_copy = os.path.join(os.path.dirname(__file__),'print_template/rast' + datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '.' + raster_path.split('/')[-1].split('.')[-1])
                        #outfile_copy = os.path.join(os.path.dirname(__file__),'print_template/outfile' + datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '.tif' )
                        plot_path = os.path.join(os.path.dirname(__file__),'print_template/plot' + datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '.jpg' )
                        p_dis_html = '' #command to add dissmissed points to HTML table
                        p_acc_html = ''  #command to add accepted points to HTML table
                        
                        #os.path.join(tempfile.gettempdir(), raster_path.split('/')[-1])                        
                        #copyfile(raster_path, raster_copy) #copping rasters to html file catalog - so html could display them
                        #copyfile(outfile, outfile_copy)
                        
                        #generating accepted points diagram
                        plot = None
                        plot = plt # matplotlib plot
                        for i in range(self.table.rowCount()):
                            if self.table.item(i,3).text() != '-' and self.table.item(i,1).text() != '-': #only for PAIR of points
                                if self.table.item(i,0).text() == 'Yes':
                                    try:
                                        x, y, vx, vy = float(self.table.item(i,3).text()),float(self.table.item(i,4).text()), float(self.table.item(i,5).text()),float(self.table.item(i,6).text())
                                    except ValueError: #if we do TPS method then we get strings '-' except walues in dx dy dxy columns
                                        x, y, vx, vy = float(self.table.item(i,3).text()),float(self.table.item(i,4).text()), 0, 0
                                    plot.scatter(x, y, color='b', zorder=0) #point
                                    plot.annotate(i + 1,xy=(x, y), xytext=(15, 15), textcoords='offset points', ha='right', va='bottom', bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),zorder=1)
                                    plot.annotate('', xy=(x, y), xytext=(x + 10*vx, y + 10*vy), arrowprops=dict(color='orange', arrowstyle="<-"),zorder=3)                        
                        plot.title('Accepted points distribution')
                        plot.axis('scaled')
                        #plot.legend(loc='upper left')
                        plot.axes().get_xaxis().set_visible(False)
                        plot.axes().get_yaxis().set_visible(False)
                        #plot.tight_layout()
                        plot.savefig(plot_path,  bbox='tight')
                        plot.clf() #clear and close
                        
                        #converting table to HTML
                        for i in range(self.table.rowCount()):
                            line = r'<tr><th>' + str(i + 1) + r'</th>'
                            for j in range (1,8):
                                line += r'<th>'+ self.table.item(i,j).text() + r'</th>'
                            line += '</tr>'
                            if self.table.item(i,0).text() == 'Yes':
                                p_acc_html += line
                            else:
                                p_dis_html += line
                          
                        temp_html = open(pdf_template_path, "r") #Reagind HTML template
                        contents = temp_html.readlines()
                        temp_html.close()
                        
                        contents.insert(26, p_dis_html) # changing HTML template according to our data  
                        contents.insert(18, p_acc_html)
                        if self.meth_combobox.currentText() == 'Helmert':
                            comp_txt, res_txt = ' -', ' -'
                        else:
                            comp_txt, res_txt = self.comp_combobox.currentText(), self.rsmp_combobox.currentText()
                        contents.insert(11, r'<p align="center"><img src="' + plot_path.split('/')[-1] + '" height="400">')
                        contents.insert(11, r'<b style="margin-left: 40px;">Input image:</b> ' + raster_path + r'<br><b style="margin-left: 40px;">Output image:</b> ' + outfile + r'<br><b style="margin-left: 40px;">Georeferencing method:</b> ' + self.meth_combobox.currentText() + '<br><b style="margin-left: 40px;">Resampling method:</b> ' + res_txt + '<br><b style="margin-left: 40px;">Compression method:</b> ' + comp_txt + '<br><b style="margin-left: 40px;">Destination EPSG:</b>' + self.label_epsg.text().split(':')[-1] + '<br><b style="margin-left: 40px;">Required points number:</b> ' + str(min_points) + '<br><b style="margin-left: 40px;">Delivered points number:</b> ' + str(len(points_xyXY)) + '<br><b style="margin-left: 40px;">Mean errors:</b><br><p style="margin-left: 60px;">' + self.label_mXY.text() + ', ' + self.label_mX.text() + ', ' + self.label_mY.text() + '</p>')
                        #contents.insert(8, r'<img src="' + raster_copy.split('/')[-1] + '" width="400" >  <img src="' + outfile_copy.split('/')[-1] + '" width="400" >') 
                         
                        
                        temporary_html = open(temporary_html_path, "w") # MAKING HTML FILE
                        contents = "".join(contents)
                        temporary_html.write(contents)
                        temporary_html.close()
                                                                             
                        html_view = QWebView() #creating html view object
                        html_view.setZoomFactor(1) #settings
                        html_view.loadFinished.connect(lambda: execpreview(html_view)) #when we load html file to html view it will trigger the printer that makes PDF
                        html_view.load(QUrl(temporary_html_path)) #loading html file into html view
                        #time.sleep(2)
                        html_view.printer = QPrinter(QPrinterInfo.defaultPrinter(),QPrinter.HighResolution) #printer settings
                        html_view.printer.setOutputFormat(QPrinter.PdfFormat)
                        html_view.printer.setOrientation(QPrinter.Portrait)
                        html_view.printer.setPaperSize(QPrinter.A4)
                        html_view.printer.setFullPage(True)
                        html_view.printer.setOutputFileName(outfile[:-4] + '_raport.pdf') #pdf raport path                   
                            
                        def execpreview(view):
                            view.print_(view.printer)
                        #execpreview(html_view)
                        '''for file in [temporary_html_path, raster_copy,outfile_copy]: #removing temporary files
                            os.remove(file)'''
      
                    if tr_method == 'order 1' or tr_method == 'order 2' or tr_method == 'order 3' or tr_method == 'tps': # for POLYNOMIAL 123 and TPS methods
                        try:
                            msg_label.setText('\nImage: ' + raster_path + '\n\nGeoreferencing method: ' + self.meth_combobox.currentText() + '\nResampling method: ' + self.rsmp_combobox.currentText() + '\nCompression method: ' + self.comp_combobox.currentText() + '\n' + self.label_epsg.text() + '\n\nRequired points number: ' + str(min_points) + '\nDelivered points number: ' + str(len(points_xyXY)) + '\n\nMean errors:\n' + self.label_mXY.text() + '\n' + self.label_mX.text() + '\n' + self.label_mY.text() + '\n\nGDAL script:\n' + 'gdal_translate -of GTiff ' + gcp_txt + '"' + raster_path + '" "' + temp_rast_path + '"' +'\n\n'+ 'gdalwarp -r '+ rs_method + ' -' + tr_method + ' -co COMPRESS=' + cp_method + ' -t_srs EPSG:' + qgis_srs_epsg + ' -dstalpha "' + temp_rast_path + '" "' + '[OUTFILE PATH - not chosen yet]' +'"')       
                            ok_button.clicked.connect(lambda: click_ok_button())
                            
                            def click_ok_button(): # georeferencing the file with GDAL
                                
                                exec_dial.close()
                                progdialog = QtGui.QProgressDialog("Georeferencing", None, 0, 100, None)
                                #progdialog.setWindowFlags(Qt.WindowStaysOnTopHint)
                                progdialog.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint ) #|Qt.WindowMaximizeButtonHint) #JANEK adding minimize and maximize buttonsprogdialog.setWindowTitle('JANEK Georeferencer')
                                outfile_path = QFileDialog.getSaveFileName(None,'Georeferenced image path',raster_path[:-len(raster_path.split('/')[-1].split('.')[-1]) - 1] + '_EPSG' + qgis_srs_epsg,'*.tif')
                                outfile_path = outfile_path.encode('utf8')
                                if outfile_path != '':
                                    progdialog.setValue(10)
                                    progdialog.show()
                                     
                                    os.system('gdal_translate -of GTiff ' + gcp_txt + '"' + raster_path + '" "' + temp_rast_path + '"')
                                    progdialog.setValue(40)
                                    os.system('gdalwarp -r '+ rs_method + ' -' + tr_method + ' -co COMPRESS=' + cp_method + ' -t_srs EPSG:' + qgis_srs_epsg + ' -dstalpha "' + temp_rast_path + '" "' + outfile_path +'"')
                                    progdialog.setValue(80)
                                    qgis.utils.iface.addRasterLayer(outfile_path.decode('utf8'), outfile_path.split('/')[-1][:-4])
                                    
                                    if pdf_checkbox.isChecked():
                                        make_pdf_rap(outfile_path)
                                        
                                    os.remove(temp_rast_path) # Delete temporary raster 
                                    progdialog.setValue(100)
                                    progdialog.close()
                        except Exception:
                            QMessageBox.warning(None, "I/O Error", "Please remove all non-ASCII chatacters from raster and output file paths.\nThen try again.")
                                
                        exec_dial.exec_()
                        
                    elif tr_method == 'helmert': # For helmert method
                        try:
                            msg_label.setText('\nImage: ' + raster_path + '\n\nGeoreferencing method: ' + self.meth_combobox.currentText() + '\nResampling method: -' + '\nCompression method: -' + '\n' + self.label_epsg.text() + '\n\nRequired points number: ' + str(min_points) + '\nDelivered points number: ' + str(len(points_xyXY)) + '\n\nMean errors:\n' + self.label_mXY.text() + '\n' + self.label_mX.text() + '\n' + self.label_mY.text())
                            ok_button.clicked.connect(lambda: click_ok_button())
                            
                            def click_ok_button(): # georeferencing the file with GDAL
                                exec_dial.close()
                                progdialog = QtGui.QProgressDialog("Georeferencing", None, 0, 100, None)
                                #progdialog.setWindowFlags(Qt.WindowStaysOnTopHint)
                                progdialog.setWindowTitle('J Rectifier')
                                progdialog.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint ) #|Qt.WindowMaximizeButtonHint) #JANEK adding minimize and maximize buttons
                                outfile_path = QFileDialog.getSaveFileName(None,'Georeferenced image path',raster_path[:-len(raster_path.split('/')[-1].split('.')[-1]) - 1].decode('utf8') + '_EPSG' + qgis_srs_epsg,'*.tif')
                                outfile_path = outfile_path
                                if outfile_path != '':                                
                                                               
                                    progdialog.show()
                                    progdialog.setValue(10)
                                    #convert to tiff (before transformation)
                                    os.system('gdal_translate -of GTiff -a_srs EPSG:' + qgis_srs_epsg + ' -co COMPRESS=JPEG "' + raster_path + '" "' + outfile_path + '"')
                                    progdialog.setValue(30)
                                    
                                    # change list of points into numpy array
                                    for i in range(len(points_xyXY)): #converting all 'str' to 'float'
                                        for j in range(len(points_xyXY[i])):
                                            points_xyXY[i][j] = float(points_xyXY[i][j])
                                            
                                    gcp_table = np.array(points_xyXY) #JANEK Converting list of lists into NUMPY table, for faster and easier calculations
                                    helm_params = janek_transformations.JanekTransform().helm_trans(gcp_table)[6]
                                    a, b, c, d = helm_params[0], helm_params[1], helm_params[2], helm_params[3] #GET TRANSFORMATION PARAMETERS 
                                    progdialog.setValue(60)
                                    
                                    # doing helmert transformation of tiff
                                    rast_src = gdal.Open(outfile_path, 1) # open rasterfile to transform
                                    new_geotransform = (c, b, a, d, a, -b) # new gro-transformation tuple
                                    rast_src.SetGeoTransform(new_geotransform)                                
                                    if rast_src.GetRasterBand(1).GetNoDataValue() is None: #changing nodata value to 0, so it will be invisible
                                        rast_src.GetRasterBand(1).SetNoDataValue(0.0)
                                    rast_src = None #close/save tif
                                    progdialog.setValue(80)
                                    # adding to map 
                                    qgis.utils.iface.addRasterLayer(outfile_path.decode('utf8'), outfile_path.split('/')[-1][:-4])
                                    
                                    
                                    if pdf_checkbox.isChecked():
                                        progdialog.setValue(90)
                                        make_pdf_rap(outfile_path)
                                        
                                    progdialog.setValue(100)
                                    progdialog.close()
                        except Exception:
                            QMessageBox.warning(None, "I/O Error", "Please remove all non-ASCII chatacters from raster and output file paths.\nThen try again.")
                    
                        exec_dial.exec_()
                        
                    else:
                        QMessageBox.information(None, "Georeferencing error", "Not available")
                else:
                    QMessageBox.information(None, "Georeferencing error", self.meth_combobox.currentText() + ' method requires minimum ' + str(min_points) + ' points' )
            else:
                QMessageBox.information(None, "Georeferencing error", 'There is no image to georeference' )
                          
        def click_btn_add_point(self):
            global point_plug_path, point_qgis_path 

            if point_plug_path is not None and point_qgis_path is not None:            
                #JANEK Changing mouse cursor in canvases
                cr_cursor = QCursor()
                cr_cursor.setShape(Qt.CrossCursor)
                ar_cursor = QCursor()
                ar_cursor.setShape(Qt.ArrowCursor) 
                
                #JANEK unchecking Edit Point button - if checked
                if self.btn_edit_point.isChecked():
                    self.btn_edit_point.setChecked(False)
                
                #JANEK the main function of the button - fillin' in the table with data obtained by clicking in map canvases
                #JANEK Referes to the classes that are described down below
                tool1 = self.PointTool(self.canvas, self.table, self.meth_combobox, self.label_mXY, self.label_mX, self.label_mY, self.zoom_checkbox, qgis.utils.iface.mapCanvas(), self.rsmp_combobox, self.comp_combobox)
                tool2 = self.PointTool2(self.canvas, self.table)
                tool_qgs1 = self.PointTool_MainQgisCanvas(qgis.utils.iface.mapCanvas(), self.table, self.meth_combobox, self.label_mXY, self.label_mX, self.label_mY, self.zoom_checkbox, self.canvas, self.rsmp_combobox, self.comp_combobox)
                tool_qgs2 = self.PointTool2_MainQgisCanvas(qgis.utils.iface.mapCanvas(), self.table)

                if self.btn_add_point.isChecked(): 
                    #JANEK CHANGE CURSOR
                    self.canvas.setCursor(cr_cursor)
                    qgis.utils.iface.mapCanvas().setCursor(cr_cursor)
                    #JANEK CHANGE MAPTOOL for plugin canvas and qgis canvas
                    self.canvas.setMapTool(tool1)
                    qgis.utils.iface.mapCanvas().setMapTool(tool_qgs1)
                else:
                    self.canvas.setCursor(ar_cursor)
                    qgis.utils.iface.mapCanvas().setCursor(ar_cursor)
                    self.canvas.setMapTool(tool2)
                    qgis.utils.iface.mapCanvas().setMapTool(tool_qgs2)
            else:
                QMessageBox.information(None, "Add points error", "You must load an image before adding points")
                self.btn_add_point.setChecked(False)
        
        def toggle_btn_add_point(self): #just changing style
            if self.btn_add_point.isChecked(): #when button is pressed
                self.btn_add_point.setStyleSheet(u'')
            else:
                self.btn_add_point.setStyleSheet('border: none;')
        
        def click_btn_del_point(self):
            global point_plug_path, point_plug_path 

            if len(self.table.selectionModel().selectedRows()) > 0:
                selected_rows = self.table.selectionModel().selectedRows()
                if len(selected_rows) != 0:
                    first_row = None
                    for i in reversed(selected_rows): #list must be reversed so the loop finds right rows
                        self.table.removeRow(i.row()) #find a row with ALL COLUMNS selected an then delete it
                        first_row = i.row()
                        #JANEK deleting points from layers, and updating "ID" field in attribute table
                        if point_plug_path is not None and point_qgis_path is not None:
                            driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                            dataSource_p = driver.Open(point_plug_path,1)
                            dataSource_q = driver.Open(point_qgis_path,1)
                            vlayer_p = dataSource_p.GetLayer() #gettin inside layers
                            vlayer_q = dataSource_q.GetLayer()
                            for layer in [vlayer_p, vlayer_q]: #the same action for both disp layers
                                for feature in layer: #iterating features until delate
                                    if feature.GetField('ID') == i.row() + 1: #find a feature with atribute ID the same as selected row
                                        layer.DeleteFeature(feature.GetFID()) #delating the feature, GetFID tells which feature of the layer we found
                                layer.ResetReading()
                                for feature in layer: #iterating features and updating ID field
                                    if feature.GetField('ID') > i.row() + 1: #find a feature with atribute ID bigger than selected row
                                        new_id = feature.GetField('ID') - 1
                                        feature.SetField('ID', new_id) #setting new value for ID (decresed by 1)
                                        layer.SetFeature(feature) #assignin changed feature to layer
                                        feature.Destroy()
                                layer.ResetReading()
                                        
                    if self.table.rowCount() <= first_row:
                        self.table.selectRow(first_row - 1)
                    else:
                        self.table.selectRow(first_row)
                            
                    dataSource_p = None #closing dataset - something like saving changes
                    dataSource_q = None
                    '''self.canvas.refreshAllLayers()#refreshin canvases
                    self.canvas.refresh() 
                    qgis.utils.iface.mapCanvas().refreshAllLayers()
                    qgis.utils.iface.mapCanvas().refresh()'''
                    self.table.refresh(self) #refreshin table
             
            else:
                QMessageBox.information(None, "Delete point error", "Select the table rows with the points you want to delete")
                
        def click_btn_edit_point(self):
            global point_plug_path, point_plug_path 

            #JANEK Changing mouse cursor in canvases
            cr_cursor = QCursor()
            cr_cursor.setShape(Qt.CrossCursor)
            ar_cursor = QCursor()
            ar_cursor.setShape(Qt.ArrowCursor)
            
            #JANEK unchecking ADD Point button - if checked
            if self.btn_add_point.isChecked():
                self.btn_add_point.setChecked(False)
            
            #JANEK the main function of the button - fillin' in the table with data obtained by clicking in map canvases
            #JANEK Referes to the classes that are described down below
            tool_edit = self.PointTool_edit(self.canvas, self.table, self.meth_combobox, self.label_mXY, self.label_mX, self.label_mY, self.zoom_checkbox, qgis.utils.iface.mapCanvas(), self.rsmp_combobox, self.comp_combobox)
            tool_noedit = self.PointTool2(self.canvas, self.table)
            tool_qgs_edit = self.PointTool_edit_MainQgisCanvas(qgis.utils.iface.mapCanvas(), self.table, self.meth_combobox, self.label_mXY, self.label_mX, self.label_mY, self.zoom_checkbox, self.canvas, self.rsmp_combobox, self.comp_combobox)
            tool_qgs_noedit = self.PointTool2_MainQgisCanvas(qgis.utils.iface.mapCanvas(), self.table)

            if self.btn_edit_point.isChecked(): 
                #JANEK CHANGE CURSOR
                self.canvas.setCursor(cr_cursor)
                qgis.utils.iface.mapCanvas().setCursor(cr_cursor)
                #JANEK CHANGE MAPTOOL for plugin canvas and qgis canvas
                self.canvas.setMapTool(tool_edit)
                qgis.utils.iface.mapCanvas().setMapTool(tool_qgs_edit)
            else:
                self.canvas.setCursor(ar_cursor)
                qgis.utils.iface.mapCanvas().setCursor(ar_cursor)
                self.canvas.setMapTool(tool_noedit)
                qgis.utils.iface.mapCanvas().setMapTool(tool_qgs_noedit)
        
        def toggle_btn_edit_point(self): #just changing style
            if self.btn_edit_point.isChecked(): #when button is pressed - 
                self.btn_edit_point.setStyleSheet(u'')
            else:
                self.btn_edit_point.setStyleSheet('border: none;')
            '''#JANEK this function sent a signal whenever button is clicked or changed by clicking another button
            #JANEk it xyXY columns fillable when the button is pressed and not fillable when it's released
            #if self.table.rowCount() > 0
            for row in range(self.table.rowCount()):
                for col in [1, 2, 3, 4]:
                    if self.table.item(row, col).text() != '-':
                        if self.btn_edit_point.isChecked(): #when button is pressed - fields are editable, if released - they are not editable
                            self.table.item(row, col).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled )
                        else:
                            self.table.item(row, col).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )'''
        
        def click_btn_type_points(self):
            global point_plug_path, point_plug_path
            if len(self.table.selectedItems()) > 0: #works when points are selected
    
                type_coords_dial = QDialog()
                type_coords_dial.setGeometry(400, 400, 470, 100)
                type_coords_dial.setWindowFlags(Qt.WindowStaysOnTopHint)
                type_coords_dial.setWindowTitle('Type Coordinates Values')
                type_coords_dial.setFixedSize(470, 100) #block size
                type_coords_dial.setWindowIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/icon.png') )) #setting icon

                #JANEK=======LineEdits (place for inputs)
                x_le = QLineEdit(type_coords_dial)
                x_le.move(20,10)
                x_le.setFixedWidth(200)
                x_le.setValidator(QDoubleValidator(-0.99,99.99,15))

                y_le = QLineEdit(type_coords_dial)
                y_le.move(20,40)
                y_le.setFixedWidth(200)
                y_le.setValidator(QDoubleValidator(-0.99,99.99,15))

                X_le = QLineEdit(type_coords_dial)
                X_le.move(250,10)
                X_le.setFixedWidth(200)
                X_le.setValidator(QDoubleValidator(-0.99,99.99,15))

                Y_le = QLineEdit(type_coords_dial)
                Y_le.move(250,40)
                Y_le.setFixedWidth(200)
                Y_le.setValidator(QDoubleValidator(-0.99,99.99,15))

                #JANEK=========Labels
                x_label = QLabel(type_coords_dial)
                x_label.move(10, 10)
                x_label.setText('x')
                y_label = QLabel(type_coords_dial)
                y_label.move(10, 40)
                y_label.setText('y')
                X_label = QLabel(type_coords_dial)
                X_label.move(240, 10)
                X_label.setText('X')
                Y_label = QLabel(type_coords_dial)
                Y_label.move(240, 40)
                Y_label.setText('Y')
                
                row = self.table.selectedItems()[-1].row() # get the row
                #Fillin in lineedits according to table:
                pre_coords = [] #remember provided coordinates in case of use CANCEL button by user
                for i in [[1, x_le], [2, y_le], [3, X_le], [4, Y_le]]: # 1,2,3,4 are numbers of xyXY columns x_le... are lineedits variables to setText
                    pre_coords.append(self.table.item(row,i[0]).text())
                    if self.table.item(row,i[0]).text() != '-':
                        i[1].setText(self.table.item(row,i[0]).text())


                #JANEK=========Buttons and it's functions
                ok_button = QPushButton(type_coords_dial)
                ok_button.setText('Ok')
                ok_button.move(290,70)
                ok_button.clicked.connect(lambda: click_ok_button())
                ok_button.setAutoDefault(False)
                
                apply_button = QPushButton(type_coords_dial)
                apply_button.setText('Apply')
                apply_button.move(210,70)
                apply_button.clicked.connect(lambda: click_apply_button())
                apply_button.setAutoDefault(False)
                
                cancel_button = QPushButton(type_coords_dial)
                cancel_button.setText('Cancel')
                cancel_button.move(370,70)
                cancel_button.clicked.connect(lambda: click_cancel_button())
                cancel_button.setAutoDefault(False)

                def click_ok_button():
                    click_apply_button()
                    type_coords_dial.close()
                    
                def click_cancel_button():
                    #change table
                    for i in range(4):
                        self.table.item(row,i+1).setText(pre_coords[i]) #setting unchanged xyXY values in table
                        
                     #change vector layers 
                    if point_plug_path is not None and point_qgis_path is not None: # if layers exist
                        for lr_path in [point_plug_path, point_qgis_path]:
                            if lr_path == point_plug_path:
                                old_x , old_y = pre_coords[0], pre_coords[1]
                            else:
                                old_x , old_y = pre_coords[2], pre_coords[3]
                        
                            if old_x != '-' and old_y != '-': 
                                        
                                driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                                dataSource = driver.Open(lr_path,1)
                                vlayer = dataSource.GetLayer() #gettin inside layers
                                point_exist = 0 # using this value it checks is there is a point with this ID in layer
                                #1 updating a point in vector layer                        
                                for feature in vlayer: #iterating features until delate
                                    if feature.GetField('ID') == row + 1: #find a feature with atribute ID the same as selected row and update coordinates
                                        point_exist = 1
                                        new_point = ogr.Geometry(ogr.wkbPoint)
                                        new_point.AddPoint(float(old_x), float(old_y))
                                        feature.SetField('ID', row + 1)
                                        if self.table.item(row,0).text() == 'Yes':
                                            feature.SetField('ACCEPT', 1)
                                        else:
                                            feature.SetField('ACCEPT', 0)
                                        feature.SetGeometry(new_point)
                                        vlayer.SetFeature(feature)
                                
                                if point_exist ==0:
                                    featureDefn = vlayer.GetLayerDefn()
                                    feature = ogr.Feature(featureDefn)
                                    point = ogr.Geometry(ogr.wkbPoint)
                                    point.AddPoint(float(old_x), float(old_y))
                                    feature.SetGeometry(point)
                                    feature.SetField('ID', row + 1)
                                    if self.table.item(row,0).text() == 'Yes':
                                        feature.SetField('ACCEPT', 1)
                                    else:
                                        feature.SetField('ACCEPT', 0)
                                    
                                    vlayer.CreateFeature(feature)
                                 
                        
                                
                            else:    
                                driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                                dataSource = driver.Open(lr_path,1)
                                vlayer = dataSource.GetLayer() #gettin inside layers
                                for feature in vlayer: #iterating features until delate
                                    if feature.GetField('ID') == row + 1: #find a feature with atribute ID the same as selected row and update coordinates
                                        vlayer.DeleteFeature(feature.GetFID()) # deleting feature to GetFID helps you find ID which is assosiated wich every feature in every layer. it is not the same as in 'ID' field
                                
                                feature = None #closing feature
                                dataSource = None
                                
                    self.table.refresh(self)
                    type_coords_dial.close()
                     
                def click_apply_button():
                    #if x_le.text() == '' and y_le.text() == '' and X_le.text() == '' and Y_le.text() == '': # if everything is empty
                        #type_coords_dial.close()
                        
                    if (x_le.text() == '' and y_le.text() != '') or (x_le.text() != '' and y_le.text() == '') or (X_le.text() == '' and Y_le.text() != '') or (X_le.text() != '' and Y_le.text() == '') : #if only 1 of coordinates is filled
                        QMessageBox.information(None, "Input error", "You must input both x and y coordinates for a point")
                        
                    else: #elif (x_le.text() != '' and y_le.text() != '') or (X_le.text() != '' and Y_le.text() != ''): # if xy or XY are filled
                        #Changing values in table
                        for i in [[1, x_le], [2, y_le], [3, X_le], [4, Y_le]]: # 1,2,3,4 are numbers of xyXY columns x_le... are lineedits variables to setText
                            try:
                                if float(i[1].text()):
                                    self.table.item(row, i[0]).setText(i[1].text())
                            except ValueError:
                                self.table.item(row, i[0]).setText('-')
                                
                        #Changing values in vector layer
                        if point_plug_path is not None and point_qgis_path is not None: # if layers exist
                            for new_xy in [[x_le.text(), y_le.text(), 1], [X_le.text(), Y_le.text(), 2]]: #3rd variable in lists (1,2) is for check is we are changing xy or XY
                                
                                col_x, col_y = None, None
                                if new_xy[2] == 1:
                                    col_x, col_y, lr_path = 1, 2, point_plug_path
                                else:
                                    col_2, col_y, lr_path = 3, 4, point_qgis_path
                                
                                if new_xy[0] != '' and  new_xy[1] != '': #checkin if we change xy or XY
                                                                       
                                    new_x, new_y = float(new_xy[0]), float(new_xy[1]) #assignin new FLOAT (not txt) values
                                
                                    driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                                    dataSource = driver.Open(lr_path,1)
                                    vlayer = dataSource.GetLayer() #gettin inside layers
                                    point_exist = 0 # using this value it checks is there is a point with this ID in layer
                                    #1 updating a point in vector layer                        
                                    for feature in vlayer: #iterating features until delate
                                        if feature.GetField('ID') == row + 1: #find a feature with atribute ID the same as selected row and update coordinates
                                            point_exist = 1
                                            new_point = ogr.Geometry(ogr.wkbPoint)
                                            new_point.AddPoint(new_x, new_y)
                                            feature.SetField('ID', row + 1)
                                            if self.table.item(row,0).text() == 'Yes':
                                                feature.SetField('ACCEPT', 1)
                                            else:
                                                feature.SetField('ACCEPT', 0)
                                            feature.SetGeometry(new_point)
                                            vlayer.SetFeature(feature)
                                            
                                    if point_exist ==0:
                                        featureDefn = vlayer.GetLayerDefn()
                                        feature = ogr.Feature(featureDefn)
                                        point = ogr.Geometry(ogr.wkbPoint)
                                        point.AddPoint(new_x, new_y)
                                        feature.SetGeometry(point)
                                        feature.SetField('ID', row + 1)
                                        if self.table.item(row,0).text() == 'Yes':
                                            feature.SetField('ACCEPT', 1)
                                        else:
                                            feature.SetField('ACCEPT', 0)
                                        
                                        vlayer.CreateFeature(feature)
                                 
                                    
                                    feature = None #closing feature
                                    dataSource = None #closing dataset - something like saving changes
                                    
                                elif new_xy[0] == '' and  new_xy[1] == '': # if fields are empty - we delete a point if exist in vect layer
                                    driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                                    dataSource = driver.Open(lr_path,1)
                                    vlayer = dataSource.GetLayer() #gettin inside layers
                                    for feature in vlayer: #iterating features until delate
                                        if feature.GetField('ID') == row + 1: #find a feature with atribute ID the same as selected row and update coordinates
                                            vlayer.DeleteFeature(feature.GetFID()) # deleting feature to GetFID helps you find ID which is assosiated wich every feature in every layer. it is not the same as in 'ID' field

                                    feature = None #closing feature
                                    dataSource = None #closing dataset - something like saving changes
                        
                            self.table.refresh(self) #refreshin table
                                            
                type_coords_dial.show()
            else:
                QMessageBox.information(None, "Selection error", "Select a point to edit")
                    
        def click_btn_save_points(self):
            global point_plug_path, point_plug_path
            if self.table.rowCount() != 0:
                saved_points_path = QFileDialog.getSaveFileName(None,'Georeferenced image path',raster_path + '.points', '*.points')
                if saved_points_path != '':
                    saved_points_file = open(saved_points_path, "w")
                    saved_points_file.write('mapX,mapY,pixelX,pixelY,enable\n')
                    for i in range(self.table.rowCount()):
                        for j in [3, 4, 1, 2]:
                            if self.table.item(i,j).text() == '-':
                                saved_points_file.write(('-9999999999,'))
                            else:
                                saved_points_file.write((self.table.item(i,j).text() + ','))
                        if self.table.item(i,0).text() == 'Yes':
                            saved_points_file.write('1\n')
                        else:
                            saved_points_file.write('0\n')
                    saved_points_file.close()
            else:
                QMessageBox.information(None, "Save points error", "No points in table")       
            
        def click_btn_read_points(self):
            global point_plug_path, point_plug_path, raster_path 

            if point_plug_path is not None and point_qgis_path is not None:
                global start_row
                start_row = 0 #the row where we start to adding points if user dont want to delete current points
                
                #JANEK Ask about clearing the table
                if self.table.rowCount() != 0: #if there are some points in table
                    clear_tab_dial = QDialog()
                    clear_tab_dial.setMinimumWidth(100)
                    clear_tab_dial.setGeometry(400, 400, 100, 60)
                    clear_tab_dial.setWindowFlags(Qt.WindowStaysOnTopHint)
                    clear_tab_dial.setWindowTitle('Import points')
                    clear_tab_dial.setFixedSize(470, 100) #block size

                    #JANEK=========Labels
                    msg_label = QLabel(clear_tab_dial)
                    msg_label.move(100, 20)
                    msg_label.setText('Do you want to remove existing points?')
      
                    #JANEK=========Buttons and it's functions
                    yes_button = QPushButton(clear_tab_dial)
                    yes_button.setText('Yes')
                    yes_button.move(290,65)
                    yes_button.clicked.connect(lambda: click_yes_button())
                    
                    no_button = QPushButton(clear_tab_dial)
                    no_button.setText('No')
                    no_button.move(370,65)
                    no_button.clicked.connect(lambda: click_no_button())

                    def click_yes_button():
                        global start_row
                        clear_tab_dial.close()
                        for i in reversed(range(self.table.rowCount())):
                            self.table.removeRow(i)
                        
                    
                    def click_no_button():
                        global start_row
                        clear_tab_dial.close()
                        start_row = self.table.rowCount()
                        
                    clear_tab_dial.exec_()
                    
                points_arr_path = QFileDialog.getOpenFileName(None,"Select points file",raster_path[:-len(raster_path.split('/')[-1])],"*.points") #Getting the file (from raster catalog)
               
                if points_arr_path != '': #Updating the table
                    points_arr = np.loadtxt(points_arr_path, skiprows=1, delimiter=',') #creating numpy array with points from file [X,Y,x,y,ACCEPT(1 or 0)], empty values are '-99999999999999'
                    for i in range(len(points_arr)): # if u got empty table and 2 points in file it will add new rows [0 and 1st], if you got 2 points in file and 5 in table it will add new rows [5th and 6th]
                        added_row = start_row + i
                        self.table.insertRow(added_row)
                        
                        for j in [[1,2], [2,3], [3,0], [4,1]]: #because table is accept,x,y,X,Y and file is X,Y,x,y,accept (because that is .points format from georeferencer ;-/)
                            if points_arr[i, j[1]] != -9999999999:
                                self.table.setItem(added_row, j[0], QtGui.QTableWidgetItem(''))
                                self.table.item(added_row, j[0]).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                                self.table.item(added_row, j[0]).setText(str(points_arr[i, j[1]]))
                            else:
                                self.table.setItem(added_row, j[0], QtGui.QTableWidgetItem(''))
                                self.table.item(added_row, j[0]).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                                self.table.item(added_row, j[0]).setText('-')
                            
                        for k in [0, 5, 6, 7]:  # JANEK set columns accept/dx/dy/dxy gray and non-editable
                            self.table.setItem(added_row, k, QtGui.QTableWidgetItem(''))
                            self.table.item(added_row,k).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                            self.table.item(added_row,k).setBackgroundColor(Qt.lightGray)
                            if k !=0:
                                self.table.item(added_row, k).setText('-') # Fill boxes dx dy dxy
                        if points_arr[i, 4] == 1:
                            self.table.item(added_row, 0).setText('Yes')
                            self.table.item(added_row,0).setTextColor(Qt.green) #Janek ACCEPT ROW
                            self.table.item(added_row,0).setTextAlignment(Qt.AlignCenter) #Janek ACCEPT ROW
                        else:
                            self.table.item(added_row, 0).setText('No')
                            self.table.item(added_row,0).setTextColor(Qt.red) #Janek ACCEPT ROW
                            self.table.item(added_row,0).setTextAlignment(Qt.AlignCenter) #Janek ACCEPT ROW
                            
                    #self.table.refresh(self)

                #UPDATING vect layers (deleta all points and read them once again from table)
                driver = ogr.GetDriverByName('ESRI shapefile')
                for lr_path in [point_plug_path,point_qgis_path]:
                    dataSource = driver.Open(lr_path, 1) #open layer 1- edition mode
                    layer = dataSource.GetLayer()
                    for feature in layer: #delating all points
                        layer.DeleteFeature(feature.GetFID())
                    feature = None
                    
                    featureDefn = layer.GetLayerDefn()                    
                    if lr_path == point_plug_path:
                        col_x, col_y = 1, 2 # number of columns in self.table
                    else:
                        col_x, col_y = 3, 4
                    for i in range(self.table.rowCount()): #creating new points and adding them to layer
                        if self.table.item(i, col_x).text() != '-' and self.table.item(i, col_y).text() != '-':
                            feature = ogr.Feature(featureDefn)
                            new_point = ogr.Geometry(ogr.wkbPoint)
                            x = float(self.table.item(i, col_x).text())
                            y = float(self.table.item(i, col_y).text())
                            new_point.AddPoint(x, y)
                            feature.SetGeometry(new_point)
                            feature.SetField('ID', i + 1)
                            if self.table.item(i, 0).text() == 'Yes':
                                feature.SetField('ACCEPT', 1)
                            else:
                                feature.SetField('ACCEPT', 0)
                            layer.CreateFeature(feature)
                            
                    feature = None
                    dataSource = None
                    
                    self.table.refresh(self)
                    '''self.canvas.refreshAllLayers()#refreshin canvases
                    self.canvas.refresh() 
                    qgis.utils.iface.mapCanvas().refreshAllLayers()
                    qgis.utils.iface.mapCanvas().refresh()   '''                 
            
            else:
                QMessageBox.information(None, "Read points error", "Load an image first")

        def toggled_err_checkbox(self):
            global err_plug_path, err_qgis_path
            
            try:
                if err_plug_path is not None and err_qgis_path is not None:
                    driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                    dataSource_p = driver.Open(err_plug_path,1)
                    dataSource_q = driver.Open(err_qgis_path,1)
                    vlayer_p = dataSource_p.GetLayer() #gettin inside layers
                    vlayer_q = dataSource_q.GetLayer()
                    for layer in [vlayer_p, vlayer_q]: #the same action for both disp layers
                        for feature in layer: #iterating features until delate
                            new_show = None
                            if self.err_checkbox.isChecked():
                                new_show = 1
                            else:
                                new_show = 0
                            feature.SetField('SHOW', new_show)
                            layer.SetFeature(feature) #assignin changed feature to layer
                            feature.Destroy()
                    layer.ResetReading()
                    
                    dataSource_p = None #closing dataset - something like saving changes
                    dataSource_q = None
                    self.table.refresh(self) #refreshin table
                    
            except Exception:
                pass
  
        def click_btn_highlight(self): #changing vector layer style
            global point_plug_path, point_qgis_path, raster_path, lyr_plug# self.highlight
            #NEEDED PATHS OF STYLES
            plug_style_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),'styles/plug_canv_style.qml'))
            qgis_style_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),'styles/qgis_canv_style.qml'))
            plug_style_h_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),'styles/plug_canv_style_h.qml'))
            qgis_style_h_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),'styles/qgis_canv_style_h.qml'))
            
            if raster_path is not None:
                if self.highlight is False: 
                    self.btn_highlight.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/highlight_2.png') ))
                    self.highlight = True #CHANGING GLOBAL VARIABLE
                    #CHANGING STYLE  normal>highlighted
                    lyr_plug.loadNamedStyle(plug_style_h_path) # changing layer style in plugin canvas
                    lyr_plug.triggerRepaint() #reloading/refteshing
                    layers = qgis.utils.iface.legendInterface().layers()# changing layer style in qgis canvas
                    for layer in layers:
                        if layer.source() == point_qgis_path:
                            layer.loadNamedStyle(qgis_style_h_path)
                            layer.triggerRepaint()                    
                    
                else:
                    self.btn_highlight.setIcon( QIcon(os.path.join(os.path.dirname(__file__),'icons/highlight.png') ))
                    self.highlight = False
                    #CHANGING STYLE  highlighted>normal
                    lyr_plug.loadNamedStyle(plug_style_path) # changing layer style in plugin canvas
                    lyr_plug.triggerRepaint() #reloading/refteshing
                    layers = qgis.utils.iface.legendInterface().layers()# changing layer style in qgis canvas
                    for layer in layers:
                        if layer.source() == point_qgis_path:
                            layer.loadNamedStyle(qgis_style_path)
                            layer.triggerRepaint()    
                    
                return self.highlight

  
                        #JANEK ====================Getting point coordinates to GPC table by mouse chlicking!!====================
#JANEK Used later in click_btn_add_point()!  Probably it could be solved easier :-)
#JANEK if PointTool works - mouse clicking deliver new points to GCP table, if PointTool2 works - it doesn't deliver them

        class PointTool(QgsMapTool): #JANEK pointtool that makes mouse clicking adding GCP points
            global point_plug_path, point_qgis_path
            
            def __init__(self, canvas, table, meth_combobox, label_mXY, label_mX, label_mY, zoom_checkbox, other_canvas, rsmp_combobox, comp_combobox):
                QgsMapTool.__init__(self, canvas)
                self.canvas = canvas
                self.table = table
                self.meth_combobox = meth_combobox
                self.label_mXY = label_mXY
                self.label_mX = label_mX
                self.label_mY = label_mY
                self.zoom_checkbox = zoom_checkbox
                self.other_canvas = other_canvas
                self.rsmp_combobox = rsmp_combobox
                self.comp_combobox = comp_combobox
                
                
            def canvasPressEvent(self, event):
                pass

            def canvasMoveEvent(self, event):
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)

            def canvasReleaseEvent(self, event):
                global table_full
                table_full = True
                #row_count = self.table.rowCount() #JANEK used for checkbox
                #gcp_table_len = len(gcp_table)
                current_id = None #Janek this parameter is used to get a correct ID number of the point in attribute table of displayed vector layer
                modifiers = QtGui.QApplication.keyboardModifiers() # the attribute is to check if SHIFT is pressed - it changes the function action
                                
                #Get the click
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)
                #point = [x, y] # when you click in plugin canvas you dont want to get map coordinates but image (pixels) coordinates
                #JANEK ======== Passing x y values to table
                for i in range(self.table.rowCount()):
                    if  self.table.item(i,1).text() == '-' and self.table.item(i,2).text() == '-' and table_full == True and modifiers != QtCore.Qt.ShiftModifier: #Modifier is to check if SHIFT is pressed
                        self.table.setItem(i, 1, QtGui.QTableWidgetItem(str(point[0])))
                        self.table.setItem(i, 2, QtGui.QTableWidgetItem(str(point[1])))
                        self.table.item(i, 1).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                        self.table.item(i, 2).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                        table_full = False
                        current_id = i + 1
                
                if table_full == True:
                    self.table.insertRow(self.table.rowCount())
                    self.table.setItem(self.table.rowCount()-1, 1, QtGui.QTableWidgetItem(str(point[0])))
                    self.table.setItem(self.table.rowCount()-1, 2, QtGui.QTableWidgetItem(str(point[1])))
                    self.table.setItem(self.table.rowCount()-1, 3, QtGui.QTableWidgetItem(str('-')))
                    self.table.setItem(self.table.rowCount()-1, 4, QtGui.QTableWidgetItem(str('-')))
                    self.table.item(self.table.rowCount()-1,1).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                    self.table.item(self.table.rowCount()-1,2).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                    self.table.item(self.table.rowCount()-1,3).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled ) #enabling also empty cells
                    self.table.item(self.table.rowCount()-1,4).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                    current_id = self.table.rowCount()
                    #self.table.selectRow(current_id - 1)
                    #zoom_to_points(current_id)
                    
                    for i in [0, 5, 6, 7]:  # JANEK set columns accept/dx/dy/dxy gray and non-editable
                        self.table.setItem(self.table.rowCount()-1,i,QtGui.QTableWidgetItem(''))
                        self.table.item(self.table.rowCount()-1,i).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                        self.table.item(self.table.rowCount()-1,i).setBackgroundColor(Qt.lightGray)
                        if i !=0:
                            self.table.item(self.table.rowCount()-1,i).setText('-') # Fill boxes dx dy dxy
                    self.table.item(self.table.rowCount()-1,0).setText('Yes') #Janek ACCEPT ROW
                    self.table.item(self.table.rowCount()-1,0).setTextColor(Qt.green) #Janek ACCEPT ROW
                    self.table.item(self.table.rowCount()-1,0).setTextAlignment(Qt.AlignCenter) #Janek ACCEPT ROW
                    
                #JANEK ===== SELCTING a ROW
                selected_row = self.table.rowCount() - 1 #default row to selection - the last row in table
                for i in reversed(range(self.table.rowCount())):
                    if self.table.item(i, 1).text() == '-' or self.table.item(i, 3).text() == '-': #if there is come not filled row we'll change selection
                        selected_row = i
                
                self.table.selectRow(selected_row)
                                
                # JANEK============JANEK ADDING POINT to displayed vect layer
                driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                dataSource = driver.Open(point_plug_path,1)
                vlayer = dataSource.GetLayer() #gettin inside layer
                featureDefn = vlayer.GetLayerDefn()#gettin feature deffinition
                feature = ogr.Feature(featureDefn) #creatin feature object based on feature definition
                new_point = ogr.Geometry(ogr.wkbPoint) #creatin a geometry object
                new_point.AddPoint(point[0], point[1]) #assignin coordinates to geometry object
                feature.SetGeometry(new_point) #assignin geometry to feature
                feature.SetField('ACCEPT', 1) #assignin field values for feature accept = 1
                feature.SetField('ID', current_id)
                vlayer.CreateFeature(feature) #importing designed feature to the layer
                feature = None #closing feature
                dataSource = None #closing dataset - something like saving changes
                                
                #JANEK =========== AUTO ZOOM # because of helmert calculations it is little bit different for QGIS canvas
                #zoom_to_points(current_id)
                
                #JANEK =========== AUTO ZOOM # because of helmert calculations it is little bit different for QGIS canvas
                if self.zoom_checkbox.isChecked(): # works only when user wants it
                    # 1 - makin a numpy array of points
                    points_xyXY = [] #list of lists of points [x,y,X,Y]
                    accepted_indexes = [] #JANEK indexes of points accepted by user
                    for i in range(self.table.rowCount()): #JANEK - makin a list of accepted values in table
                        if self.table.item(i,0).text() == 'Yes' and self.table.item(i,1).text() != '-' and self.table.item(i,2).text() != '-' and self.table.item(i,3).text() != '-' and self.table.item(i,4).text() != '-':
                            points_xyXY.append([float(self.table.item(i,1).text()), float(self.table.item(i,2).text()), float(self.table.item(i,3).text()), float(self.table.item(i,4).text())])
                            accepted_indexes.append(i)
                    gcp_table = np.array(points_xyXY) #JANEK Converting list of lists into NUMPY table, for faster and easier calculations
                    # 2 - check if autozooming (predicting next point) is possible, and if it is nessesery (if point on other canvas is not picked already)
                    if len(gcp_table) > 1 and self.table.item(current_id - 1,3).text() == '-' and self.table.item(current_id - 1,4).text() == '-': #zooming #1 
                        # 3 - assignin x y values
                        x, y = point[0], point[1]
                        # 4 - calculate helmert transformation parameters 
                        helm_params = janek_transformations.JanekTransform().helm_trans(gcp_table)[6]
                        a, b, c, d = helm_params[0], helm_params[1], helm_params[2], helm_params[3]
                        # 5 - calculate predicted X Y values to know where to zoom (HELMERT TRANSFORMATION FORMULA)
                        predX = c + b*x - a*y
                        predY = d + a*x + b*y
                        #predY = (b*Y - d*b - a*X + a*c)/(a*a + b*b)
                        #predX = (X + a*predy - c)/b
                        #6 - scaling out and zoomin to the area of predicted next point
                        self.other_canvas.zoomScale(self.other_canvas.scale()*1.5) # zoomin out x1.5
                        self.other_canvas.setCenter(QgsPoint(predX, predY)) # seting center on predicted point
                        #self.canvas.zoomScale(self.other_canvas.scale()*1.5) # zoomin out x1.5
                        #self.canvas.setCenter(QgsPoint(predX, predY)) # seting center on predicted point
                        
                    elif len(gcp_table) > 1 and self.table.item(current_id - 1,3).text() != '-' and self.table.item(current_id - 1,4).text() != '-': #zooming 1 - next xy exist, but XY is empty
                        if self.table.item(current_id, 3) is not None and self.table.item(current_id, 4) is not None: # if next XY exist 
                            if self.table.item(current_id, 3).text() != '-' and self.table.item(current_id, 4).text() != '-': # and of course is not empty
                                X, Y = float(self.table.item(current_id, 3).text()), float(self.table.item(current_id, 4).text())
                                helm_params = janek_transformations.JanekTransform().helm_trans(gcp_table)[6]
                                a, b, c, d = helm_params[0], helm_params[1], helm_params[2], helm_params[3]
                                predy = (b*Y - d*b - a*X + a*c)/(a*a + b*b)
                                predx = (X + a*predy - c)/b
                                
                                #self.canvas.setCenter(QgsPoint(X, Y))
                                self.canvas.setCenter(QgsPoint(predx, predy))
                                #self.other_canvas.zoomScale(self.other_canvas.scale()*1.5) # zoomin out x1.5
                                #self.other_canvas.setCenter(QgsPoint(predx, predy)) # seting center on predicted point
                                self.other_canvas.setCenter(QgsPoint(X, Y)) # seting center on predicted point
                                self.table.selectRow(current_id)
                                
                self.table.refresh(self) 
                
            def activate(self):
                pass

            def deactivate(self):
                pass

            def isZoomTool(self):
                return False

            def isTransient(self):
                return False

            def isEditTool(self):
                return True
    
        class PointTool2(QgsMapTool):#JANEK just a regular pointtool, dont do nothing in fact.
            def __init__(self, canvas, table):
                QgsMapTool.__init__(self, canvas)
                self.canvas = canvas
                self.table = table

            def canvasPressEvent(self, event):
                pass

            def canvasMoveEvent(self, event):
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)

            def canvasReleaseEvent(self, event):
                #Get the click
               pass
            def activate(self):
                pass

            def deactivate(self):
                pass

            def isZoomTool(self):
                return False

            def isTransient(self):
                return False

            def isEditTool(self):
                return True
                
        class PointTool_MainQgisCanvas(QgsMapTool): #JANEK pointtool that makes mouse clicking adding GCP points
            global point_plug_path, point_qgis_path
            
            def __init__(self, canvas, table, meth_combobox, label_mXY, label_mX, label_mY, zoom_checkbox, other_canvas, rsmp_combobox, comp_combobox):
                QgsMapTool.__init__(self, canvas)
                self.canvas = canvas
                self.table = table
                self.meth_combobox = meth_combobox
                self.label_mXY = label_mXY
                self.label_mX = label_mX
                self.label_mY = label_mY
                self.zoom_checkbox = zoom_checkbox
                self.other_canvas = other_canvas
                self.rsmp_combobox = rsmp_combobox
                self.comp_combobox = comp_combobox

            def canvasPressEvent(self, event):
                pass

            def canvasMoveEvent(self, event):
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)

            def canvasReleaseEvent(self, event):
                global table_full #JANEK global needed in the loop below (adding points do table)
                table_full = True
                #row_count = self.table.rowCount() #JANEK used for checkbox
                current_id = None #Janek this parameter is used to get a correct ID number of the point in attribute table of displayed vector layer
                #gcp_table_len = len(gcp_table)
                modifiers = QtGui.QApplication.keyboardModifiers()
                
                #Get the click
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)
                #JANEK ======== Passing X Y values to table
                for i in range(self.table.rowCount()):
                    if self.table.item(i,3).text() == '-' and self.table.item(i,4).text() == '-' and table_full == True and modifiers != QtCore.Qt.ShiftModifier:
                        self.table.setItem(i, 3, QtGui.QTableWidgetItem(str(point[0])))
                        self.table.setItem(i, 4, QtGui.QTableWidgetItem(str(point[1])))
                        self.table.item(i, 3).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                        self.table.item(i ,4).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                        table_full = False
                        current_id = i + 1
                        self.table.selectRow(current_id - 1)
                        #zoom_to_points(current_id)
                
                if table_full == True:
                    self.table.insertRow(self.table.rowCount())
                    self.table.setItem(self.table.rowCount()-1, 3, QtGui.QTableWidgetItem(str(point[0])))
                    self.table.setItem(self.table.rowCount()-1, 4, QtGui.QTableWidgetItem(str(point[1])))
                    self.table.setItem(self.table.rowCount()-1, 1, QtGui.QTableWidgetItem(str('-')))
                    self.table.setItem(self.table.rowCount()-1, 2, QtGui.QTableWidgetItem(str('-')))
                    self.table.item(self.table.rowCount()-1,3).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                    self.table.item(self.table.rowCount()-1,4).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                    self.table.item(self.table.rowCount()-1,1).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled ) #enabling also "empty" cells
                    self.table.item(self.table.rowCount()-1,2).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                    current_id = self.table.rowCount()
                    #self.table.selectRow(current_id - 1)
                    #self.table.selectRow(i)
                    
                    for i in [0, 5, 6, 7]:  # JANEK set Items to some columnes and make them gray and non-editable
                        self.table.setItem(self.table.rowCount()-1,i,QtGui.QTableWidgetItem(''))
                        self.table.item(self.table.rowCount()-1,i).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                        self.table.item(self.table.rowCount()-1,i).setBackgroundColor(Qt.lightGray)
                        if i !=0:
                            self.table.item(self.table.rowCount()-1,i).setText('-') # Fill boxes dx dy dxy
                    self.table.item(self.table.rowCount()-1,0).setText('Yes') #Janek ACCEPT ROW
                    self.table.item(self.table.rowCount()-1,0).setTextColor(Qt.green) #Janek ACCEPT ROW
                    self.table.item(self.table.rowCount()-1,0).setTextAlignment(Qt.AlignCenter) #Janek ACCEPT ROW
                    
                #JANEK ===== SELCTING a ROW
                
                for i in reversed(range(self.table.rowCount())):
                    if self.table.item(i, 1).text() == '-' or self.table.item(i, 3).text() == '-': #if there is come not filled row we'll change selection
                        selected_row = i
                
                selected_row = self.table.rowCount() - 1 #default row to selection - the last row in table
                
                self.table.selectRow(selected_row)
                                    
                #JANEK =============ADDING POINT to displayed vect layer
                driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                dataSource = driver.Open(point_qgis_path,1)
                vlayer = dataSource.GetLayer() #gettin inside layer
                featureDefn = vlayer.GetLayerDefn()#gettin feature deffinition
                feature = ogr.Feature(featureDefn) #creatin feature object based on feature definition
                new_point = ogr.Geometry(ogr.wkbPoint) #creatin a geometry object
                new_point.AddPoint(point[0], point[1]) #assignin coordinates to geometry object
                feature.SetGeometry(new_point) #assignin geometry to feature
                feature.SetField('ACCEPT', 1) #assignin field values for feature accept = 1
                feature.SetField('ID', current_id)
                vlayer.CreateFeature(feature) #importing designed feature to the layer
                feature = None
                dataSource = None #closing dataset - something like saving changes
                
                #JANEK =========== AUTO ZOOM # because of helmert calculations it is little bit different for plugin canvas
                #zoom_to_points(cuttent_id)
                #self.table.selectRow(current_id)
                
                #current_id = selected_row + 1 # changing current-id value, now its something differend - used to zooming
                
                #JANEK =========== AUTO ZOOM # because of helmert calculations it is little bit different for plugin canvas
                if self.zoom_checkbox.isChecked(): # works only when user wants it
                    # 1 - makin a numpy array of points
                    points_xyXY = [] #list of lists of points [x,y,X,Y]
                    accepted_indexes = [] #JANEK indexes of points accepted by user
                    for i in range(self.table.rowCount()): #JANEK - makin a list of accepted values in table
                        if self.table.item(i,0).text() == 'Yes' and self.table.item(i,1).text() != '-' and self.table.item(i,2).text() != '-' and self.table.item(i,3).text() != '-' and self.table.item(i,4).text() != '-':
                            points_xyXY.append([float(self.table.item(i,1).text()), float(self.table.item(i,2).text()), float(self.table.item(i,3).text()), float(self.table.item(i,4).text())])
                            accepted_indexes.append(i)
                    gcp_table = np.array(points_xyXY) #JANEK Converting list of lists into NUMPY table, for faster and easier calculations
                    # 2 - check if autozooming (predicting next point) is possible, and if it is nessesery (if point on other canvas is not picked already)
                    if len(gcp_table) > 1 and self.table.item(current_id - 1,1).text() == '-' and self.table.item(current_id - 1,2).text() == '-': #zooming if 
                        # 3 - assignin x y values
                        X, Y = point[0], point[1]
                        # 4 - calculate helmert transformation parameters 
                        helm_params = janek_transformations.JanekTransform().helm_trans(gcp_table)[6]
                        a, b, c, d = helm_params[0], helm_params[1], helm_params[2], helm_params[3]
                        # 5 - calculate predicted X Y values to know where to zoom (HELMERT TRANSFORMATION FORMULA)
                        predy = (b*Y - d*b - a*X + a*c)/(a*a + b*b)
                        predx = (X + a*predy - c)/b
                        #predx = c + b*x - a*y
                        #predy = d + a*x + b*y
                        #6 - scaling out and zoomin to the area of predicted next point
                        self.other_canvas.zoomScale(self.other_canvas.scale()*1.5) # zoomin out x1.5
                        self.other_canvas.setCenter(QgsPoint(predx, predy)) # seting center on predicted point
                        #self.canvas.zoomScale(self.other_canvas.scale()*1.5) # zoomin out x1.5
                        #self.canvas.setCenter(QgsPoint(predx, predy)) # seting center on predicted point
                    
                    elif len(gcp_table) > 1 and self.table.item(current_id - 1,1).text() != '-' and self.table.item(current_id - 1,2).text() != '-': #zooming 1 - next xy exist, but XY is empty
                        if self.table.item(current_id, 1) is not None and self.table.item(current_id, 2) is not None: # if next xy exist 
                            if self.table.item(current_id, 1).text() != '-' and self.table.item(current_id, 2).text() != '-': # and of course is not empty
                                x, y = float(self.table.item(current_id, 1).text()), float(self.table.item(current_id, 2).text())
                                helm_params = janek_transformations.JanekTransform().helm_trans(gcp_table)[6]
                                a, b, c, d = helm_params[0], helm_params[1], helm_params[2], helm_params[3]
                                predX = c + b*x - a*y
                                predY = d + a*x + b*y
                                #self.canvas.setCenter(QgsPoint(x, y))
                                self.canvas.setCenter(QgsPoint(predX, predY))
    #                            self.other_canvas.zoomScale(self.other_canvas.scale()*1.5) # zoomin out x1.5
                                #self.other_canvas.setCenter(QgsPoint(predX, predY)) # seting center on predicted point
                                self.other_canvas.setCenter(QgsPoint(x, y))
                                self.table.selectRow(current_id)
               
                self.table.refresh(self) #JANEK refreshing table function is described above - it calculates dx dy dxy
                '''self.canvas.refreshAllLayers()
                self.canvas.refresh() #refreshin canvas
                self.other_canvas.refreshAllLayers()
                self.other_canvas.refresh()'''
                
            def activate(self):
                pass

            def deactivate(self):
                pass

            def isZoomTool(self):
                return False

            def isTransient(self):
                return False

            def isEditTool(self):
                return True
    
        class PointTool2_MainQgisCanvas(QgsMapTool):#JANEK just a regular pointtool, dont do nothing in fact.
            def __init__(self, canvas, table):
                QgsMapTool.__init__(self, canvas)
                self.canvas = canvas
                self.table = table

            def canvasPressEvent(self, event):
                pass

            def canvasMoveEvent(self, event):
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)

            def canvasReleaseEvent(self, event):
                #Get the click
               pass
            def activate(self):
                pass

            def deactivate(self):
                pass

            def isZoomTool(self):
                return False

            def isTransient(self):
                return False

            def isEditTool(self):
                return True
                
        class PointTool_edit(QgsMapTool): #JANEK pointtool that makes mouse clicking adding GCP points (for EDIT POINT purposes)
            global point_plug_path, point_qgis_path
            
            def __init__(self, canvas, table, meth_combobox, label_mXY, label_mX, label_mY, zoom_checkbox, other_canvas, rsmp_combobox, comp_combobox):
                QgsMapTool.__init__(self, canvas)
                self.canvas = canvas
                self.table = table
                self.meth_combobox = meth_combobox
                self.label_mXY = label_mXY
                self.label_mX = label_mX
                self.label_mY = label_mY
                self.zoom_checkbox = zoom_checkbox
                self.other_canvas = other_canvas
                self.rsmp_combobox = rsmp_combobox
                self.comp_combobox = comp_combobox
                
            def canvasPressEvent(self, event):
                pass

            def canvasMoveEvent(self, event):
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)

            def canvasReleaseEvent(self, event):
                #global table_full
                table_full = True
                current_id = None #Janek this parameter is used to get a correct ID number of the point in attribute table of displayed vector layer
                #Get the click
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)
                #JANEK ======== Passing x y values to table
                if len(self.table.selectedItems()) > 0: # if there is something selected in table
                    #JANEk assignin row and column and id number
                    row = self.table.selectedItems()[-1].row() 
                    id = row + 1
                    
                    #JANEk changing values in table
                    self.table.setItem(row, 1, QtGui.QTableWidgetItem(str(point[0])))
                    self.table.setItem(row, 2, QtGui.QTableWidgetItem(str(point[1])))   
                    self.table.item(row, 1).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                    self.table.item(row, 2).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )                    
                    
                    
                    # JANEK========== updating points on displayed vect layer                    
                    if point_plug_path is not None and point_qgis_path is not None:
                        driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                        dataSource = driver.Open(point_plug_path,1)
                        vlayer = dataSource.GetLayer() #gettin inside layers
                        point_exist = 0 # using this value it checks is there is a point with this ID in layer
                        
                        #1 updating a point in vector layer                        
                        for feature in vlayer: #iterating features until delate
                            if feature.GetField('ID') == id: #find a feature with atribute ID the same as selected row and update coordinates
                                point_exist = 1
                                new_point = ogr.Geometry(ogr.wkbPoint)
                                new_point.AddPoint(point[0], point[1])
                                feature.SetField('ID', id)
                                if self.table.item(row,0).text() == 'Yes':
                                    feature.SetField('ACCEPT', 1)
                                else:
                                    feature.SetField('ACCEPT', 2)
                                feature.SetGeometry(new_point)
                                vlayer.SetFeature(feature)
                                point_exist = 1
                        #2 creating a new point in vect layer (if there was no point so far)
                        if point_exist == 0:
                            featureDefn = vlayer.GetLayerDefn()#gettin feature deffinition
                            feature = ogr.Feature(featureDefn) #creatin feature object based on feature definition
                            new_point = ogr.Geometry(ogr.wkbPoint) #creatin a geometry object
                            new_point.AddPoint(float(self.table.item(id - 1,1).text()), float(self.table.item(id - 1,2).text())) #assignin coordinates to geometry object
                            feature.SetGeometry(new_point) #assignin geometry to feature
                            if self.table.item(row, 0).text() == 'Yes': #assignin field values for feature accept = 1
                                feature.SetField('ACCEPT', 1) 
                            else:
                                feature.SetField('ACCEPT', 0)
                            feature.SetField('ID', id)
                            vlayer.CreateFeature(feature) #importing designed feature to the layer
                                                    
                        feature = None #closing feature
                        dataSource = None #closing dataset - something like saving changes
                        
                    self.table.refresh(self) #JANEK refreshing table function is described above - it calculates dx dy dxy
                    '''self.canvas.refreshAllLayers()#refreshin canvas
                    self.canvas.refresh()
                    self.other_canvas.refreshAllLayers()
                    self.other_canvas.refresh()'''
                
            def activate(self):
                pass

            def deactivate(self):
                pass

            def isZoomTool(self):
                return False

            def isTransient(self):
                return False

            def isEditTool(self):
                return True
                
        class PointTool_edit_MainQgisCanvas(QgsMapTool): #JANEK pointtool that makes mouse clicking adding GCP points
            global point_plug_path, point_qgis_path
            
            def __init__(self, canvas, table, meth_combobox, label_mXY, label_mX, label_mY, zoom_checkbox, other_canvas, rsmp_combobox, comp_combobox):
                QgsMapTool.__init__(self, canvas)
                self.canvas = canvas
                self.table = table
                self.meth_combobox = meth_combobox
                self.label_mXY = label_mXY
                self.label_mX = label_mX
                self.label_mY = label_mY
                self.zoom_checkbox = zoom_checkbox
                self.other_canvas = other_canvas
                self.rsmp_combobox = rsmp_combobox
                self.comp_combobox = comp_combobox
                
            def canvasPressEvent(self, event):
                pass

            def canvasMoveEvent(self, event):
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)

            def canvasReleaseEvent(self, event):
                global table_full
                table_full = True
                current_id = None #Janek this parameter is used to get a correct ID number of the point in attribute table of displayed vector layer
                #Get the click
                x = event.pos().x()
                y = event.pos().y()

                point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)
                #JANEK ======== Passing x y values to table
                if len(self.table.selectedItems()) > 0: #if there is something selected in table
                    #JANEk assignin row and column and id number
                    row = self.table.selectedItems()[-1].row() 
                    id = row + 1
                    
                    #JANEk changing values in table
                    self.table.setItem(row, 3, QtGui.QTableWidgetItem(str(point[0])))
                    self.table.setItem(row, 4, QtGui.QTableWidgetItem(str(point[1])))
                    self.table.item(row, 3).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                    self.table.item(row, 4).setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled )
                                        
                    # JANEK========== updating points ondisplayed vect layer                    
                    if point_plug_path is not None and point_qgis_path is not None:
                        driver = ogr.GetDriverByName('ESRI shapefile') #Opening the file
                        dataSource = driver.Open(point_qgis_path,1)
                        vlayer = dataSource.GetLayer() #gettin inside layers
                        point_exist = 0 # using this value it checks is there is a point with this ID in layer
                       
                       #1 updating a point in vector layer                        
                        for feature in vlayer: #iterating features until delate
                            if feature.GetField('ID') == id: #find a feature with atribute ID the same as selected row and update coordinates
                                point_exist = 1
                                new_point = ogr.Geometry(ogr.wkbPoint)
                                new_point.AddPoint(point[0], point[1])
                                feature.SetField('ID', id)
                                if self.table.item(row,0).text() == 'Yes':
                                    feature.SetField('ACCEPT', 1)
                                else:
                                    feature.SetField('ACCEPT', 2)
                                feature.SetGeometry(new_point)
                                vlayer.SetFeature(feature)
                                point_exist = 1
                        #2 creating a new point in vect layer (if there was no point so far)
                        if point_exist == 0:
                            featureDefn = vlayer.GetLayerDefn()#gettin feature deffinition
                            feature = ogr.Feature(featureDefn) #creatin feature object based on feature definition
                            new_point = ogr.Geometry(ogr.wkbPoint) #creatin a geometry object
                            new_point.AddPoint(float(self.table.item(id - 1,3).text()), float(self.table.item(id - 1,4).text())) #assignin coordinates to geometry object
                            feature.SetGeometry(new_point) #assignin geometry to feature
                            if self.table.item(row, 0).text() == 'Yes': #assignin field values for feature accept = 1
                                feature.SetField('ACCEPT', 1) 
                            else:
                                feature.SetField('ACCEPT', 0)
                            feature.SetField('ID', id)
                            vlayer.CreateFeature(feature) #importing designed feature to the layer

                        feature = None #closing feature
                        dataSource = None #closing dataset - something like saving changes
                    
                    self.table.refresh(self) #JANEK refreshing table function is described above - it calculates dx dy dxy
                    '''self.canvas.refreshAllLayers()#refreshin canvas
                    self.canvas.refresh()
                    self.other_canvas.refreshAllLayers()
                    self.other_canvas.refresh()'''
                
            def activate(self):
                pass

            def deactivate(self):
                pass

            def isZoomTool(self):
                return False

            def isTransient(self):
                return False

            def isEditTool(self):
                return True
                
    #JANEK =====================RUN THE PLUGIN!!!!=========================
    def run(self):
        global jg_running
        if jg_running == 0: # that prevents from opening 2 windows at the same time
            dis_win = self.DisplayedWindow()
            if dis_win.window_plugin.exec_():
                pass
            