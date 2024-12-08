# -*- coding: utf-8 -*-





import random
import functools
import html
import math
import os
import os.path as osp
import re
import webbrowser
import sys
# print(sys.path)
sys.path.append('c:\\users\\aasad\\appdata\\local\\programs\\python\\python312\\lib\\site-packages')
PY3 = sys.version[0] == "3.12.4"

import imgviz
import natsort

from PyQt5 import QtCore,QtGui,QtWidgets
from PyQt5.QtGui import QBrush ,QColor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import *
from qtpy.QtCore import Qt


from labelme.ai import MODELS
from labelme.config import get_config
from labelme.label_file import LabelFile
from labelme.label_file import LabelFileError
from labelme.logger import logger
from labelme.shape import Shape
from labelme.widgets import BrightnessContrastDialog
from labelme.widgets import Canvas
from labelme.widgets import FileDialogPreview
from labelme.widgets import LabelDialog
from labelme.widgets import LabelListWidget
from labelme.widgets import LabelListWidgetItem
from labelme.widgets import ToolBar
from labelme.widgets import UniqueLabelQListWidget
from labelme.widgets import ZoomWidget
from labelme import utils
#from labelme.widgets.Detection_annotation import PersonDetectionApp
import cv2
import torch
# import torchreid
# from torchreid import models
import json
import numpy as np

from ultralytics import YOLO
from scipy.spatial.distance import euclidean
from deep_sort_realtime.deepsort_tracker import DeepSort
from deep_sort_realtime.deep_sort.nn_matching import NearestNeighborDistanceMetric
from deep_sort_realtime.deep_sort.detection import Detection
from deep_sort_realtime.deep_sort.tracker import Tracker
from shapely.geometry import  box




# import torch.nn as nn
# from torchvision.models import resnet50, ResNet50_Weights
# yolo_model = torch.hub.load('ultralytics/yolov5', 'yolov5s')

import fastreid
print(fastreid.__file__)

from fastreid.config import get_cfg
from fastreid.engine import DefaultPredictor
from sklearn.metrics.pairwise import cosine_similarity
from xml.etree.ElementTree import Element, SubElement, ElementTree





# FIXME
# - [medium] Set max zoom value to something big enough for FitWidth/Window

# TODO(unknown):
# - Zoom is too "steppy".

__appname__ = "LabelMe - Enhanced Version"
LABEL_COLORMAP = imgviz.label_colormap()


class MainWindow(QtWidgets.QMainWindow):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = 0, 1, 2

    def __init__(
        self,
        config=None,
        filename=None,
        output=None,
        output_file=None,
        output_dir=None,
        #custom_option=False,
    ):
        super(MainWindow, self).__init__()
          
        self.setWindowTitle(__appname__)
        self.setWindowIcon(QtGui.QIcon(r"labelme//icons//image.png"))
        
        # Apply styles for a modern look
        self.setStyleSheet("""
        QMainWindow {
            background-color: #2E3440;
            color: #D8DEE9;
        }
        QPushButton {
            background-color: #5c4c6a;
            color: #D8DEE9;
            border-radius: 8px;
            padding: 8px;
            border: none;
        }
        QPushButton:hover {
            background-color: #5E81AC;
        }
        QLabel {
            color: #000000;
        }
        QMenuBar {
            background-color: #3B4252;
            color: #ECEFF4;
        }
        QMenuBar::item:selected {
            background-color: #5E81AC;
        }
        """)
        
        #self.custom_option = custom_option
        
        # Additional state for video handling
        self.video_capture = None  # OpenCV VideoCapture object
        self.current_frame = 0      # Current frame number
        self.previous_features=[]
        # self.total_frames = 0       # Total number of frames in the video
        self.person_tracks = {}# Dictionary to store tracks for each person
        # Example check if the loaded file is a video (you need to set this flag somewhere)
        self.is_video = False  # This flag will be set to True when loading a video
        self.yolo_model=None
        self.fastreid_model=None
        
        self.first_detected_id=None
        self.person_id_map={}
        self.person={} # track the person across the video
        self.track_id_manager = IDManager()
        # Connect the 'annotateVideoButton' to the enable function
        self.expected_embedding_size=2048
        
        
        if output is not None:
            logger.warning("argument output is deprecated, use output_file instead")
            if output_file is None:
                output_file = output

        # see labelme/config/default_config.yaml for valid configuration
        if config is None:
            config = get_config()
        self._config = config
################################################################################################################################

        """
        Initialize the UI components, including frame controls, video controls,
        and playback functionalities.
        """
        # Central widget
        self.centralWidget = QWidget(self)
        self.mainLayout = QVBoxLayout(self.centralWidget)
        self.setCentralWidget(self.centralWidget)

        

       
        
        """
        Initialize frame navigation controls for video annotation.
        """
        # Create buttons and input field
        self.prevFrameButton = QPushButton("Previous Frame", self)
        self.nextFrameButton = QPushButton("Next Frame", self)
        self.frameNumberInput = QLineEdit(self)
        self.frameNumberInput.setPlaceholderText("Enter Frame #")

        # Create a layout for frame controls
        frameControlLayout = QHBoxLayout()
        frameControlLayout.addWidget(self.prevFrameButton)
        frameControlLayout.addWidget(self.frameNumberInput)
        frameControlLayout.addWidget(self.nextFrameButton)

        # Wrap frame controls in a widget
        self.frameControlWidget = QWidget(self)
        self.frameControlWidget.setLayout(frameControlLayout)

        # Add the widget to a dock widget
        frameControlDock = QDockWidget("Frame Control", self)
        frameControlDock.setObjectName("frameControlDock")
        frameControlDock.setWidget(self.frameControlWidget)
        self.addDockWidget(Qt.BottomDockWidgetArea, frameControlDock)

        # Connect frame navigation buttons to their functionalities
        self.prevFrameButton.clicked.connect(self.openPrevFrame)
        self.nextFrameButton.clicked.connect(self.openNextFrame)
        
        """
        Initialize video playback controls and annotation functionalities.
        """
        # Create buttons
        self.annotateVideoButton = QPushButton("Annotate Video", self)
        self.playVideoButton = QPushButton("Play", self)
        self.pauseVideoButton = QPushButton("Pause", self)
        self.stopVideoButton = QPushButton("Stop", self)

        # Create a layout for video controls
        videoControlLayout = QHBoxLayout()
        videoControlLayout.addWidget(self.annotateVideoButton)
        videoControlLayout.addWidget(self.playVideoButton)
        videoControlLayout.addWidget(self.pauseVideoButton)
        videoControlLayout.addWidget(self.stopVideoButton)

        # Wrap video controls in a widget
        self.videoControlWidget = QWidget(self)
        self.videoControlWidget.setLayout(videoControlLayout)

        # Add the widget to a dock widget
        videoControlDock = QDockWidget("Video Control", self)
        videoControlDock.setObjectName("videoControlDock")
        videoControlDock.setWidget(self.videoControlWidget)
        self.addDockWidget(Qt.BottomDockWidgetArea, videoControlDock)

        # Connect buttons to their functionalities
        self.annotateVideoButton.clicked.connect(self.annotateVideo)
        self.playVideoButton.clicked.connect(self.playVideo)
        self.pauseVideoButton.clicked.connect(self.pauseVideo)
        self.stopVideoButton.clicked.connect(self.stopVideo)
        
         # Initially disable video playback buttons
        self.playVideoButton.setEnabled(False)
        self.pauseVideoButton.setEnabled(False)
        self.stopVideoButton.setEnabled(False)

        

        

        
        
        
        
##############################################################################################################################
        # set default shape colors
        Shape.line_color = QtGui.QColor(*self._config["shape"]["line_color"])
        Shape.fill_color = QtGui.QColor(*self._config["shape"]["fill_color"])
        Shape.select_line_color = QtGui.QColor(
            *self._config["shape"]["select_line_color"]
        )
        Shape.select_fill_color = QtGui.QColor(
            *self._config["shape"]["select_fill_color"]
        )
        Shape.vertex_fill_color = QtGui.QColor(
            *self._config["shape"]["vertex_fill_color"]
        )
        Shape.hvertex_fill_color = QtGui.QColor(
            *self._config["shape"]["hvertex_fill_color"]
        )

        # Set point size from config file
        Shape.point_size = self._config["shape"]["point_size"]

        
        

        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False

        self._copied_shapes = None

        # Main widgets and related state.
        self.labelDialog = LabelDialog(
            parent=self,
            labels=self._config["labels"],
            sort_labels=self._config["sort_labels"],
            show_text_field=self._config["show_label_text_field"],
            completion=self._config["label_completion"],
            fit_to_content=self._config["fit_to_content"],
            flags=self._config["label_flags"],
        )

        self.labelFile=LabelFile()
        self.labelList = LabelListWidget()
        self.lastOpenDir = None

        self.flag_dock = self.flag_widget = None
        self.flag_dock = QtWidgets.QDockWidget(self.tr("Flags"), self)
        self.flag_dock.setObjectName("Flags")
        self.flag_widget = QtWidgets.QListWidget()
        if config["flags"]:
            self.loadFlags({k: False for k in config["flags"]})
        self.flag_dock.setWidget(self.flag_widget)
        self.flag_widget.itemChanged.connect(self.setDirty)

        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.itemDoubleClicked.connect(self._edit_label)
        self.labelList.itemChanged.connect(self.labelItemChanged)
        self.labelList.itemDropped.connect(self.labelOrderChanged)
        self.shape_dock = QtWidgets.QDockWidget(self.tr("Polygon Labels"), self)
        self.shape_dock.setObjectName("Labels")
        self.shape_dock.setWidget(self.labelList)

        self.uniqLabelList = UniqueLabelQListWidget()
        self.uniqLabelList.setToolTip(
            self.tr(
                "Select label to start annotating for it. " "Press 'Esc' to deselect."
            )
        )
        if self._config["labels"]:
            for label in self._config["labels"]:
                item = self.uniqLabelList.createItemFromLabel(label)
                self.uniqLabelList.addItem(item)
                rgb = self._get_rgb_by_label(label)
                self.uniqLabelList.setItemLabel(item, label, rgb)
        self.label_dock = QtWidgets.QDockWidget(self.tr("Label List"), self)
        self.label_dock.setObjectName("Label List")
        self.label_dock.setWidget(self.uniqLabelList)

        self.fileSearch = QtWidgets.QLineEdit()
        self.fileSearch.setPlaceholderText(self.tr("Search Filename"))
        self.fileSearch.textChanged.connect(self.fileSearchChanged)
        self.fileListWidget = QtWidgets.QListWidget()
        self.fileListWidget.itemSelectionChanged.connect(self.fileSelectionChanged)
        fileListLayout = QtWidgets.QVBoxLayout()
        fileListLayout.setContentsMargins(0, 0, 0, 0)
        fileListLayout.setSpacing(0)
        fileListLayout.addWidget(self.fileSearch)
        fileListLayout.addWidget(self.fileListWidget)
        self.file_dock = QtWidgets.QDockWidget(self.tr("File List"), self)
        self.file_dock.setObjectName("Files")
        fileListWidget = QtWidgets.QWidget()
        fileListWidget.setLayout(fileListLayout)
        self.file_dock.setWidget(fileListWidget)

        self.zoomWidget = ZoomWidget()
        self.setAcceptDrops(True)

        self.canvas = self.labelList.canvas = Canvas(
            epsilon=self._config["epsilon"],
            double_click=self._config["canvas"]["double_click"],
            num_backups=self._config["canvas"]["num_backups"],
            crosshair=self._config["canvas"]["crosshair"],
        )
        self.canvas.zoomRequest.connect(self.zoomRequest)
        self.canvas.mouseMoved.connect(
            lambda pos: self.status(f"Mouse is at: x={pos.x()}, y={pos.y()}")
        )

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidget(self.canvas)
        scrollArea.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scrollArea.verticalScrollBar(),
            Qt.Horizontal: scrollArea.horizontalScrollBar(),
        }
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        self.setCentralWidget(scrollArea)

        features = QtWidgets.QDockWidget.DockWidgetFeatures()
        for dock in ["flag_dock", "label_dock", "shape_dock", "file_dock"]:
            if self._config[dock]["closable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetClosable
            if self._config[dock]["floatable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetFloatable
            if self._config[dock]["movable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetMovable
            getattr(self, dock).setFeatures(features)
            if self._config[dock]["show"] is False:
                getattr(self, dock).setVisible(False)

        self.addDockWidget(Qt.RightDockWidgetArea, self.flag_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.label_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.shape_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)

        # Actions
        action = functools.partial(utils.newAction, self)
        shortcuts = self._config["shortcuts"]
        quit = action(
            self.tr("&Quit"),
            self.close,
            shortcuts["quit"],
            "quit",
            self.tr("Quit application"),
        )
        open_ = action(
            self.tr("&Open\n"),
            self.openFile,
            shortcuts["open"],
            "open",
            self.tr("Open image or label file"),
        )
        opendir = action(
            self.tr("Open Dir"),
            self.openDirDialog,
            shortcuts["open_dir"],
            "open",
            self.tr("Open Dir"),
        )
        openVideoAction = action(
            self.tr("&Open Video"),
            self.openVideo,
            shortcuts.get("open_video", "Ctrl+O"),
            "open",
            self.tr("Open a video file for annotation")
        )
        openNextImg = action(
            self.tr("&Next Image"),
            self.openNextImg,
            shortcuts["open_next"],
            "next",
            self.tr("Open next (hold Ctl+Shift to copy labels)"),
            enabled=False,
        )
        openPrevImg = action(
            self.tr("&Prev Image"),
            self.openPrevImg,
            shortcuts["open_prev"],
            "prev",
            self.tr("Open prev (hold Ctl+Shift to copy labels)"),
            enabled=False,
        )
        openPrevFrame = action(
            text=self.tr("Previous Frame"),
            slot=self.openPrevFrame,
            shortcut=None,
            icon="prev",  # Optional: set the icon path
            tip=self.tr("Go to the previous video frame"),
            enabled=False,
        )

        openNextFrame = action(
            text=self.tr("Next Frame"),
            slot=self.openNextFrame,
            shortcut=None,  # No shortcut
            icon="next",  # Optional: set the icon path
            tip=self.tr("Go to the next video frame"),
            enabled=False,
        )

        AnnotateVideo = action(
            text=self.tr("Annotate Video"),
            slot=self.annotateVideo,
            shortcut="Ctrl+V",  # Optional shortcut
            icon="annotation",  # Optional: set the icon path
            tip=self.tr("Annotate the video using YOLO and ReID models"),
            enabled=False,  # Enable the action by default
        )
        save = action(
            self.tr("&Save\n"),
            self.saveFile,
            shortcuts["save"],
            "save",
            self.tr("Save labels to file"),
            enabled=False,
        )
        saveAs = action(
            self.tr("&Save As"),
            self.saveFileAs,
            shortcuts["save_as"],
            "save-as",
            self.tr("Save labels to a different file"),
            enabled=False,
        )

        deleteFile = action(
            self.tr("&Delete File"),
            self.deleteFile,
            shortcuts["delete_file"],
            "delete",
            self.tr("Delete current label file"),
            enabled=False,
        )

        changeOutputDir = action(
            self.tr("&Change Output Dir"),
            slot=self.changeOutputDirDialog,
            shortcut=shortcuts["save_to"],
            icon="open",
            tip=self.tr("Change where annotations are loaded/saved"),
        )
        
        saveReIDAnnotationsAction = action(
            self.tr("Save ReID Annotations"),
            self.save_reid_annotations,
            None,  # No shortcut
            "save",
            self.tr("Save video annotations with ReID results"),
            enabled=False,
        )


        saveAuto = action(
            text=self.tr("Save &Automatically"),
            slot=lambda x: self.actions.saveAuto.setChecked(x),
            icon="save",
            tip=self.tr("Save automatically"),
            checkable=True,
            enabled=True,
        )
        saveAuto.setChecked(self._config["auto_save"])

        saveWithImageData = action(
            text=self.tr("Save With Image Data"),
            slot=self.enableSaveImageWithData,
            tip=self.tr("Save image data in label file"),
            checkable=True,
            checked=self._config["store_data"],
        )

        close = action(
            self.tr("&Close"),
            self.closeFile,
            shortcuts["close"],
            "close",
            self.tr("Close current file"),
        )

        toggle_keep_prev_mode = action(
            self.tr("Keep Previous Annotation"),
            self.toggleKeepPrevMode,
            shortcuts["toggle_keep_prev_mode"],
            None,
            self.tr('Toggle "keep previous annotation" mode'),
            checkable=True,
        )
        toggle_keep_prev_mode.setChecked(self._config["keep_prev"])

        createMode = action(
            self.tr("Create Polygons"),
            lambda: self.toggleDrawMode(False, createMode="polygon"),
            shortcuts["create_polygon"],
            "objects",
            self.tr("Start drawing polygons"),
            enabled=False,
        )
        createRectangleMode = action(
            self.tr("Create Rectangle"),
            lambda: self.toggleDrawMode(False, createMode="rectangle"),
            shortcuts["create_rectangle"],
            "objects",
            self.tr("Start drawing rectangles"),
            enabled=False,
        )
        createCircleMode = action(
            self.tr("Create Circle"),
            lambda: self.toggleDrawMode(False, createMode="circle"),
            shortcuts["create_circle"],
            "objects",
            self.tr("Start drawing circles"),
            enabled=False,
        )
        createLineMode = action(
            self.tr("Create Line"),
            lambda: self.toggleDrawMode(False, createMode="line"),
            shortcuts["create_line"],
            "objects",
            self.tr("Start drawing lines"),
            enabled=False,
        )
        createPointMode = action(
            self.tr("Create Point"),
            lambda: self.toggleDrawMode(False, createMode="point"),
            shortcuts["create_point"],
            "objects",
            self.tr("Start drawing points"),
            enabled=False,
        )
        createLineStripMode = action(
            self.tr("Create LineStrip"),
            lambda: self.toggleDrawMode(False, createMode="linestrip"),
            shortcuts["create_linestrip"],
            "objects",
            self.tr("Start drawing linestrip. Ctrl+LeftClick ends creation."),
            enabled=False,
        )
        createAiPolygonMode = action(
            self.tr("Create AI-Polygon"),
            lambda: self.toggleDrawMode(False, createMode="ai_polygon"),
            None,
            "objects",
            self.tr("Start drawing ai_polygon. Ctrl+LeftClick ends creation."),
            enabled=False,
        )
        createAiPolygonMode.changed.connect(
            lambda: self.canvas.initializeAiModel(
                name=self._selectAiModelComboBox.currentText()
            )
            if self.canvas.createMode == "ai_polygon"
            else None
        )
        createAiMaskMode = action(
            self.tr("Create AI-Mask"),
            lambda: self.toggleDrawMode(False, createMode="ai_mask"),
            None,
            "objects",
            self.tr("Start drawing ai_mask. Ctrl+LeftClick ends creation."),
            enabled=False,
        )
        createAiMaskMode.changed.connect(
            lambda: self.canvas.initializeAiModel(
                name=self._selectAiModelComboBox.currentText()
            )
            if self.canvas.createMode == "ai_mask"
            else None
        )
        
        
        editMode = action(
            self.tr("Edit Polygons"),
            self.setEditMode,
            shortcuts["edit_polygon"],
            "edit",
            self.tr("Move and edit the selected polygons"),
            enabled=False,
        )

        delete = action(
            self.tr("Delete Polygons"),
            self.deleteSelectedShape,
            shortcuts["delete_polygon"],
            "cancel",
            self.tr("Delete the selected polygons"),
            enabled=False,
        )
        duplicate = action(
            self.tr("Duplicate Polygons"),
            self.duplicateSelectedShape,
            shortcuts["duplicate_polygon"],
            "copy",
            self.tr("Create a duplicate of the selected polygons"),
            enabled=False,
        )
        copy = action(
            self.tr("Copy Polygons"),
            self.copySelectedShape,
            shortcuts["copy_polygon"],
            "copy_clipboard",
            self.tr("Copy selected polygons to clipboard"),
            enabled=False,
        )
        paste = action(
            self.tr("Paste Polygons"),
            self.pasteSelectedShape,
            shortcuts["paste_polygon"],
            "paste",
            self.tr("Paste copied polygons"),
            enabled=False,
        )
        undoLastPoint = action(
            self.tr("Undo last point"),
            self.canvas.undoLastPoint,
            shortcuts["undo_last_point"],
            "undo",
            self.tr("Undo last drawn point"),
            enabled=False,
        )
        removePoint = action(
            text=self.tr("Remove Selected Point"),
            slot=self.removeSelectedPoint,
            shortcut=shortcuts["remove_selected_point"],
            icon="edit",
            tip=self.tr("Remove selected point from polygon"),
            enabled=False,
        )

        undo = action(
            self.tr("Undo\n"),
            self.undoShapeEdit,
            shortcuts["undo"],
            "undo",
            self.tr("Undo last add and edit of shape"),
            enabled=False,
        )

        hideAll = action(
            self.tr("&Hide\nPolygons"),
            functools.partial(self.togglePolygons, False),
            shortcuts["hide_all_polygons"],
            icon="eye",
            tip=self.tr("Hide all polygons"),
            enabled=False,
        )
        showAll = action(
            self.tr("&Show\nPolygons"),
            functools.partial(self.togglePolygons, True),
            shortcuts["show_all_polygons"],
            icon="eye",
            tip=self.tr("Show all polygons"),
            enabled=False,
        )
        toggleAll = action(
            self.tr("&Toggle\nPolygons"),
            functools.partial(self.togglePolygons, None),
            shortcuts["toggle_all_polygons"],
            icon="eye",
            tip=self.tr("Toggle all polygons"),
            enabled=False,
        )
        


        help = action(
            self.tr("&Tutorial"),
            self.tutorial,
            icon="help",
            tip=self.tr("Show tutorial page"),
        )

        zoom = QtWidgets.QWidgetAction(self)
        zoomBoxLayout = QtWidgets.QVBoxLayout()
        zoomLabel = QtWidgets.QLabel(self.tr("Zoom"))
        zoomLabel.setAlignment(Qt.AlignCenter)
        zoomBoxLayout.addWidget(zoomLabel)
        zoomBoxLayout.addWidget(self.zoomWidget)
        zoom.setDefaultWidget(QtWidgets.QWidget())
        zoom.defaultWidget().setLayout(zoomBoxLayout)
        self.zoomWidget.setWhatsThis(
            str(
                self.tr(
                    "Zoom in or out of the image. Also accessible with "
                    "{} and {} from the canvas."
                )
            ).format(
                utils.fmtShortcut(
                    "{},{}".format(shortcuts["zoom_in"], shortcuts["zoom_out"])
                ),
                utils.fmtShortcut(self.tr("Ctrl+Wheel")),
            )
        )
        self.zoomWidget.setEnabled(False)

        zoomIn = action(
            self.tr("Zoom &In"),
            functools.partial(self.addZoom, 1.1),
            shortcuts["zoom_in"],
            "zoom-in",
            self.tr("Increase zoom level"),
            enabled=False,
        )
        zoomOut = action(
            self.tr("&Zoom Out"),
            functools.partial(self.addZoom, 0.9),
            shortcuts["zoom_out"],
            "zoom-out",
            self.tr("Decrease zoom level"),
            enabled=False,
        )
        zoomOrg = action(
            self.tr("&Original size"),
            functools.partial(self.setZoom, 100),
            shortcuts["zoom_to_original"],
            "zoom",
            self.tr("Zoom to original size"),
            enabled=False,
        )
        keepPrevScale = action(
            self.tr("&Keep Previous Scale"),
            self.enableKeepPrevScale,
            tip=self.tr("Keep previous zoom scale"),
            checkable=True,
            checked=self._config["keep_prev_scale"],
            enabled=True,
        )
        fitWindow = action(
            self.tr("&Fit Window"),
            self.setFitWindow,
            shortcuts["fit_window"],
            "fit-window",
            self.tr("Zoom follows window size"),
            checkable=True,
            enabled=False,
        )
        fitWidth = action(
            self.tr("Fit &Width"),
            self.setFitWidth,
            shortcuts["fit_width"],
            "fit-width",
            self.tr("Zoom follows window width"),
            checkable=True,
            enabled=False,
        )
        brightnessContrast = action(
            self.tr("&Brightness Contrast"),
            self.brightnessContrast,
            None,
            "color",
            self.tr("Adjust brightness and contrast"),
            enabled=False,
        )
        # Group zoom controls into a list for easier toggling.
        zoomActions = (
            self.zoomWidget,
            zoomIn,
            zoomOut,
            zoomOrg,
            fitWindow,
            fitWidth,
        )
        self.zoomMode = self.FIT_WINDOW
        fitWindow.setChecked(Qt.Checked)
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action(
            self.tr("&Edit Label"),
            self._edit_label,
            shortcuts["edit_label"],
            "edit",
            self.tr("Modify the label of the selected polygon"),
            enabled=False,
        )

        fill_drawing = action(
            self.tr("Fill Drawing Polygon"),
            self.canvas.setFillDrawing,
            None,
            "color",
            self.tr("Fill polygon while drawing"),
            checkable=True,
            enabled=True,
        )
        
        
        
        if self._config["canvas"]["fill_drawing"]:
            fill_drawing.trigger()

        # Label list context menu.
        labelMenu = QtWidgets.QMenu()
        utils.addActions(labelMenu, (edit, delete))
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(self.popLabelListMenu)
        
        # Assuming you have a menu or toolbar where you want to add "Open Video" functionality
        #self.openVideoAction = QtWidgets.QAction(self.tr("&Open Video"), self)
        #self.openVideoAction.setShortcut("Ctrl+V")
        #self.openVideoAction.setStatusTip(self.tr("Open a video file"))
        #self.openVideoAction.triggered.connect(self.openVideo)
        
        #self.menu.file.addAction(openVideoAction)

        #self.toolbar.addAction(self.openVideoAction)
        
        

        # Store actions for further handling.
        self.actions = utils.struct(
            saveAuto=saveAuto,
            saveWithImageData=saveWithImageData,
            changeOutputDir=changeOutputDir,
            save=save,
            saveAs=saveAs,
            open=open_,
            close=close,
            deleteFile=deleteFile,
            toggleKeepPrevMode=toggle_keep_prev_mode,
            delete=delete,
            edit=edit,
            duplicate=duplicate,
            copy=copy,
            paste=paste,
            undoLastPoint=undoLastPoint,
            undo=undo,
            removePoint=removePoint,
            createMode=createMode,
            editMode=editMode,
            createRectangleMode=createRectangleMode,
            createCircleMode=createCircleMode,
            createLineMode=createLineMode,
            createPointMode=createPointMode,
            createLineStripMode=createLineStripMode,
            createAiPolygonMode=createAiPolygonMode,
            createAiMaskMode=createAiMaskMode,
            zoom=zoom,
            zoomIn=zoomIn,
            zoomOut=zoomOut,
            zoomOrg=zoomOrg,
            keepPrevScale=keepPrevScale,
            fitWindow=fitWindow,
            fitWidth=fitWidth,
            brightnessContrast=brightnessContrast,
            zoomActions=zoomActions,
            openNextImg=openNextImg,
            openPrevImg=openPrevImg,
            openVideoAction=openVideoAction,
            openPrevFrame=openPrevFrame,
            openNextFrame=openNextFrame,
            AnnotateVideo=AnnotateVideo,
            saveReIDAnnotations=saveReIDAnnotationsAction,
            fileMenuActions=(open_, opendir, save, saveAs, close, quit),
            tool=(),
            # XXX: need to add some actions here to activate the shortcut
            editMenu=(
                edit,
                duplicate,
                copy,
                paste,
                delete,
                None,
                undo,
                undoLastPoint,
                None,
                removePoint,
                None,
                toggle_keep_prev_mode,
            ),
            # menu shown at right click
            menu=(
                createMode,
                createRectangleMode,
                createCircleMode,
                createLineMode,
                createPointMode,
                createLineStripMode,
                createAiPolygonMode,
                createAiMaskMode,
                editMode,
                edit,
                duplicate,
                copy,
                paste,
                delete,
                undo,
                undoLastPoint,
                removePoint,
            ),
            onLoadActive=(
                close,
                createMode,
                createRectangleMode,
                createCircleMode,
                createLineMode,
                createPointMode,
                createLineStripMode,
                createAiPolygonMode,
                createAiMaskMode,
                editMode,
                brightnessContrast,
            ),
            onShapesPresent=(saveAs, hideAll, showAll, toggleAll),
        )

        self.canvas.vertexSelected.connect(self.actions.removePoint.setEnabled)

        self.menus = utils.struct(
            file=self.menu(self.tr("&File")),
            edit=self.menu(self.tr("&Edit")),
            view=self.menu(self.tr("&View")),
            help=self.menu(self.tr("&Help")),
            recentFiles=QtWidgets.QMenu(self.tr("Open &Recent")),
            labelList=labelMenu,
        )

        utils.addActions(
            self.menus.file,
            (
                open_,
                openNextImg,
                openPrevImg,
                openPrevFrame,
                openNextFrame,
                AnnotateVideo,
                opendir,
                openVideoAction,
                self.menus.recentFiles,
                save,
                saveAs,
                saveAuto,
                changeOutputDir,
                saveWithImageData,
                close,
                deleteFile,
                None,
                quit,
            ),
        )
        #self.menu.file.addAction(openVideoAction)
        utils.addActions(self.menus.help, (help,))
        utils.addActions(
            self.menus.view,
            (
                self.flag_dock.toggleViewAction(),
                self.label_dock.toggleViewAction(),
                self.shape_dock.toggleViewAction(),
                self.file_dock.toggleViewAction(),
                None,
                fill_drawing,
                None,
                hideAll,
                showAll,
                toggleAll,
                None,
                zoomIn,
                zoomOut,
                zoomOrg,
                keepPrevScale,
                None,
                fitWindow,
                fitWidth,
                None,
                brightnessContrast,
                
            ),
        )

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        utils.addActions(self.canvas.menus[0], self.actions.menu)
        utils.addActions(
            self.canvas.menus[1],
            (
                action("&Copy here", self.copyShape),
                action("&Move here", self.moveShape),
            ),
        )

        selectAiModel = QtWidgets.QWidgetAction(self)
        selectAiModel.setDefaultWidget(QtWidgets.QWidget())
        selectAiModel.defaultWidget().setLayout(QtWidgets.QVBoxLayout())
        #
        selectAiModelLabel = QtWidgets.QLabel(self.tr("AI Model"))
        selectAiModelLabel.setAlignment(QtCore.Qt.AlignCenter)
        selectAiModel.defaultWidget().layout().addWidget(selectAiModelLabel)
        #
        self._selectAiModelComboBox = QtWidgets.QComboBox()
        selectAiModel.defaultWidget().layout().addWidget(self._selectAiModelComboBox)
        model_names = [model.name for model in MODELS]
        self._selectAiModelComboBox.addItems(model_names)
        if self._config["ai"]["default"] in model_names:
            model_index = model_names.index(self._config["ai"]["default"])
        else:
            logger.warning(
                "Default AI model is not found: %r",
                self._config["ai"]["default"],
            )
            model_index = 0
        self._selectAiModelComboBox.setCurrentIndex(model_index)
        self._selectAiModelComboBox.currentIndexChanged.connect(
            lambda: self.canvas.initializeAiModel(
                name=self._selectAiModelComboBox.currentText()
            )
            if self.canvas.createMode in ["ai_polygon", "ai_mask"]
            else None
        )

        self.tools = self.toolbar("tool")
        self.actions.tool = (
            open_,
            opendir,
            openVideoAction,
            openPrevImg,
            openNextImg,
            openPrevFrame,
            openNextFrame,
            AnnotateVideo,
            saveReIDAnnotationsAction,
            save,
            deleteFile,
            None,
            createMode,
            editMode,
            duplicate,
            delete,
            undo,
            brightnessContrast,
            None,
            fitWindow,
            zoom,
            None,
            selectAiModel,
            
        )
        #self.toolbar.addAction(self.openVideoAction)
        # Apply enhanced toolbar features here
        self.tools.setButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.tools.addSeparator()
        
        # Set the visibility of the "Next Frame" action based on some condition
        self.tools.setActionVisible(self.actions.openNextFrame, True) 
        
        # Enable the "Next Frame" button only when in video mode and not at the last frame
        self.tools.setActionVisible(self.actions.openNextFrame, self.is_video and self.current_frame < self.total_frames - 1)

        # Dynamically style the toolbar buttons based on the user's preference or current context
        self.tools.setButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)

        self.statusBar().showMessage(str(self.tr("%s started.")) % __appname__)
        self.statusBar().show()

        if output_file is not None and self._config["auto_save"]:
            logger.warn(
                "If `auto_save` argument is True, `output_file` argument "
                "is ignored and output filename is automatically "
                "set as IMAGE_BASENAME.json."
            )
        self.output_file = output_file
        self.output_dir = output_dir

        # Application state.
        self.image = QtGui.QImage()
        self.imagePath = None
        self.recentFiles = []
        self.maxRecent = 7
        self.otherData = None
        self.zoom_level = 100
        self.fit_window = False
        self.zoom_values = {}  # key=filename, value=(zoom_mode, zoom_value)
        self.brightnessContrast_values = {}
        self.scroll_values = {
            Qt.Horizontal: {},
            Qt.Vertical: {},
        }  # key=filename, value=scroll_value

        if filename is not None and osp.isdir(filename):
            self.importDirImages(filename, load=False)
        else:
            self.filename = filename

        if config["file_search"]:
            self.fileSearch.setText(config["file_search"])
            self.fileSearchChanged()

        # XXX: Could be completely declarative.
        # Restore application settings.
        self.settings = QtCore.QSettings("labelme", "labelme")
        self.recentFiles = self.settings.value("recentFiles", []) or []
        size = self.settings.value("window/size", QtCore.QSize(600, 500))
        position = self.settings.value("window/position", QtCore.QPoint(0, 0))
        state = self.settings.value("window/state", QtCore.QByteArray())
        self.resize(size)
        self.move(position)
        # or simply:
        # self.restoreGeometry(settings['window/geometry']
        self.restoreState(state)

        # Populate the File menu dynamically.
        self.updateFileMenu()
        # Since loading the file may take some time,
        # make sure it runs in the background.
        if self.filename is not None:
            self.queueEvent(functools.partial(self.loadFile, self.filename))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # self.firstStart = True
        # if self.firstStart:
        #    QWhatsThis.enterWhatsThisMode()

    
    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            utils.addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName("%sToolBar" % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            utils.addActions(toolbar, actions)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        return toolbar



    # Support Functions

    def noShapes(self):
        return not len(self.labelList)

    def addDetectionAlgorithmComboBox(self):
        
        
        
        
        
        detection_label=QtWidgets.QLabel(self.tr("Detection Model"))
        detection_label.setAlignment(QtCore.Qt.AlignCenter)
        
        
        # Create a dropdown combo box for selecting the detection algorithm
        self.algorithmSelector = QComboBox(self)
        self.algorithmSelector.addItem("YOLOv8")
        self.algorithmSelector.addItem("Haar Cascade")
        self.algorithmSelector.addItem("SSD")
        self.algorithmSelector.addItem("OpenPose")
        self.algorithmSelector.setCurrentIndex(0)  # Default to YOLOv8

        # Add the combo box to the toolbar
        self.tools.addWidget(detection_label)
        self.tools.addWidget(self.algorithmSelector)
        
        
        
        # Connect the combo box selection to a method
        self.algorithmSelector.currentIndexChanged.connect(self.onAlgorithmChanged)
        

        # Store the default detection algorithm selection
        self.selected_detection_algorithm = self.algorithmSelector.currentText()

    def onAlgorithmChanged(self):
        """Handler when the detection algorithm is changed by the user."""
        self.selected_detection_algorithm = self.algorithmSelector.currentText()
        print(f"Detection Algorithm changed to: {self.selected_detection_algorithm}")
        
    
    def populateModeActions(self):
        tool, menu = self.actions.tool, self.actions.menu
        self.tools.clear()
        utils.addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        utils.addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (
            self.actions.createMode,
            self.actions.createRectangleMode,
            self.actions.createCircleMode,
            self.actions.createLineMode,
            self.actions.createPointMode,
            self.actions.createLineStripMode,
            self.actions.createAiPolygonMode,
            self.actions.createAiMaskMode,
            self.actions.editMode,
        )
        utils.addActions(self.menus.edit, actions + self.actions.editMenu)
        # Add the "Detection Algorithm" ComboBox to the toolbar
        self.addDetectionAlgorithmComboBox()
        
    def setDirty(self):
        # Even if we autosave the file, we keep the ability to undo
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)

        if self._config["auto_save"] or self.actions.saveAuto.isChecked():
            label_file = osp.splitext(self.imagePath)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = osp.join(self.output_dir, label_file_without_path)
            self.saveLabels(label_file)
            return
        self.dirty = True
        self.actions.save.setEnabled(True)
        title = __appname__
        if self.filename is not None:
            title = "{} - {}*".format(title, self.filename)
        self.setWindowTitle(title)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.createMode.setEnabled(True)
        self.actions.createRectangleMode.setEnabled(True)
        self.actions.createCircleMode.setEnabled(True)
        self.actions.createLineMode.setEnabled(True)
        self.actions.createPointMode.setEnabled(True)
        self.actions.createLineStripMode.setEnabled(True)
        self.actions.createAiPolygonMode.setEnabled(True)
        self.actions.createAiMaskMode.setEnabled(True)
        title = __appname__
        if self.filename is not None:
            title = "{} - {}".format(title, self.filename)
        self.setWindowTitle(title)

        if self.hasLabelFile():
            self.actions.deleteFile.setEnabled(True)
        else:
            self.actions.deleteFile.setEnabled(False)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QtCore.QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.labelList.clear()
        self.filename = None
        self.imagePath = None
        self.imageData = None
        self.labelFile = None
        self.otherData = None
        self.canvas.resetState()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filename):
        if filename in self.recentFiles:
            self.recentFiles.remove(filename)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filename)

    # Callbacks

    def undoShapeEdit(self):
        self.canvas.restoreShape()
        self.labelList.clear()
        self.loadShapes(self.canvas.shapes)
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)

    def tutorial(self):
        url = "https://github.com/labelmeai/labelme/tree/main/examples/tutorial"  # NOQA
        webbrowser.open(url)

    def toggleDrawingSensitive(self, drawing=True):
        """Toggle drawing sensitive.

        In the middle of drawing, toggling between modes should be disabled.
        """
        self.actions.editMode.setEnabled(not drawing)
        self.actions.undoLastPoint.setEnabled(drawing)
        self.actions.undo.setEnabled(not drawing)
        self.actions.delete.setEnabled(not drawing)

    def toggleDrawMode(self, edit=True, createMode="polygon"):
        draw_actions = {
            "polygon": self.actions.createMode,
            "rectangle": self.actions.createRectangleMode,
            "circle": self.actions.createCircleMode,
            "point": self.actions.createPointMode,
            "line": self.actions.createLineMode,
            "linestrip": self.actions.createLineStripMode,
            "ai_polygon": self.actions.createAiPolygonMode,
            "ai_mask": self.actions.createAiMaskMode,
        }

        self.canvas.setEditing(edit)
        self.canvas.createMode = createMode
        if edit:
            for draw_action in draw_actions.values():
                draw_action.setEnabled(True)
        else:
            for draw_mode, draw_action in draw_actions.items():
                draw_action.setEnabled(createMode != draw_mode)
        self.actions.editMode.setEnabled(not edit)

    def setEditMode(self):
        self.toggleDrawMode(True)

    def updateFileMenu(self):
        current = self.filename

        def exists(filename):
            return osp.exists(str(filename))

        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f != current and exists(f)]
        for i, f in enumerate(files):
            icon = utils.newIcon("labels")
            action = QtWidgets.QAction(
                icon, "&%d %s" % (i + 1, QtCore.QFileInfo(f).fileName()), self
            )
            action.triggered.connect(functools.partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def validateLabel(self, label):
        # no validation
        if self._config["validate_label"] is None:
            return True

        for i in range(self.uniqLabelList.count()):
            label_i = self.uniqLabelList.item(i).data(Qt.UserRole)
            if self._config["validate_label"] in ["exact"]:
                if label_i == label:
                    return True
        return False

    def _edit_label(self, value=None):
        if not self.canvas.editing():
            return

        items = self.labelList.selectedItems()
        if not items:
            logger.warning("No label is selected, so cannot edit label.")
            return

        shape = items[0].shape()

        if len(items) == 1:
            edit_text = True
            edit_flags = True
            edit_group_id = True
            edit_description = True
        else:
            edit_text = all(item.shape().label == shape.label for item in items[1:])
            edit_flags = all(item.shape().flags == shape.flags for item in items[1:])
            edit_group_id = all(
                item.shape().group_id == shape.group_id for item in items[1:]
            )
            edit_description = all(
                item.shape().description == shape.description for item in items[1:]
            )

        if not edit_text:
            self.labelDialog.edit.setDisabled(True)
            self.labelDialog.labelList.setDisabled(True)
        if not edit_flags:
            for i in range(self.labelDialog.flagsLayout.count()):
                self.labelDialog.flagsLayout.itemAt(i).setDisabled(True)
        if not edit_group_id:
            self.labelDialog.edit_group_id.setDisabled(True)
        if not edit_description:
            self.labelDialog.editDescription.setDisabled(True)

        text, flags, group_id, description = self.labelDialog.popUp(
            text=shape.label if edit_text else "",
            flags=shape.flags if edit_flags else None,
            group_id=shape.group_id if edit_group_id else None,
            description=shape.description if edit_description else None,
        )

        if not edit_text:
            self.labelDialog.edit.setDisabled(False)
            self.labelDialog.labelList.setDisabled(False)
        if not edit_flags:
            for i in range(self.labelDialog.flagsLayout.count()):
                self.labelDialog.flagsLayout.itemAt(i).setDisabled(False)
        if not edit_group_id:
            self.labelDialog.edit_group_id.setDisabled(False)
        if not edit_description:
            self.labelDialog.editDescription.setDisabled(False)

        if text is None:
            assert flags is None
            assert group_id is None
            assert description is None
            return

        self.canvas.storeShapes()
        for item in items:
            self._update_item(
                item=item,
                text=text if edit_text else None,
                flags=flags if edit_flags else None,
                group_id=group_id if edit_group_id else None,
                description=description if edit_description else None,
            )

    def _update_item(self, item, text, flags, group_id, description):
        if not self.validateLabel(text):
            self.errorMessage(
                self.tr("Invalid label"),
                self.tr("Invalid label '{}' with validation type '{}'").format(
                    text, self._config["validate_label"]
                ),
            )
            return

        shape = item.shape()

        if text is not None:
            shape.label = text
        if flags is not None:
            shape.flags = flags
        if group_id is not None:
            shape.group_id = group_id
        if description is not None:
            shape.description = description

        self._update_shape_color(shape)
        if shape.group_id is None:
            item.setText(
                '{} <font color="#{:02x}{:02x}{:02x}">●</font>'.format(
                    html.escape(shape.label), *shape.fill_color.getRgb()[:3]
                )
            )
        else:
            item.setText("{} ({})".format(shape.label, shape.group_id))
        self.setDirty()
        if self.uniqLabelList.findItemByLabel(shape.label) is None:
            item = self.uniqLabelList.createItemFromLabel(shape.label)
            self.uniqLabelList.addItem(item)
            rgb = self._get_rgb_by_label(shape.label)
            self.uniqLabelList.setItemLabel(item, shape.label, rgb)

    def fileSearchChanged(self):
        self.importDirImages(
            self.lastOpenDir,
            pattern=self.fileSearch.text(),
            load=False,
        )

    def fileSelectionChanged(self):
        items = self.fileListWidget.selectedItems()
        if not items:
            return
        item = items[0]

        if not self.mayContinue():
            return

        currIndex = self.imageList.index(str(item.text()))
        if currIndex < len(self.imageList):
            filename = self.imageList[currIndex]
            if filename:
                self.loadFile(filename)

    # React to canvas signals.
    def shapeSelectionChanged(self, selected_shapes):
        self._noSelectionSlot = True
        for shape in self.canvas.selectedShapes:
            shape.selected = False
        self.labelList.clearSelection()
        if not hasattr(self.canvas, 'selectedShapes') or not isinstance(self.canvas.selectedShapes, list):
            print("Warning: selectedShapes is not a list or undefined. Resetting to an empty list.")
            self.canvas.selectedShapes = []
        for shape in self.canvas.selectedShapes:
            shape.selected = True
            item = self.labelList.findItemByShape(shape)
            self.labelList.selectItemByShape(item)
            self.labelList.scrollToItem(item)
        self._noSelectionSlot = False
        n_selected = len(selected_shapes)
        self.actions.delete.setEnabled(n_selected)
        self.actions.duplicate.setEnabled(n_selected)
        self.actions.copy.setEnabled(n_selected)
        self.actions.edit.setEnabled(n_selected)
    
    ##### when I would liek to add the labels on the video from the detection will sue this method###
    # def addLabel(self, shape):
    #     if shape.group_id is None:
    #         text = shape.label
    #     else:
    #         text = "{} ({})".format(shape.label, shape.group_id)
    #     label_list_item = LabelListWidgetItem(text, shape)
    #     self.labelList.addItem(label_list_item)
    #     if self.uniqLabelList.findItemByLabel(shape.label) is None:
    #         item = self.uniqLabelList.createItemFromLabel(shape.label)
    #         self.uniqLabelList.addItem(item)
    #         rgb = self._get_rgb_by_label(shape.label)
    #         self.uniqLabelList.setItemLabel(item, shape.label, rgb)
    #     self.labelDialog.addLabelHistory(shape.label)
    #     for action in self.actions.onShapesPresent:
    #         action.setEnabled(True)

    #     self._update_shape_color(shape)
    #     label_list_item.setText(
    #         '{} <font color="#{:02x}{:02x}{:02x}">●</font>'.format(
    #             html.escape(text), *shape.fill_color.getRgb()[:3]
    #         )
    #     )
    
    def addLabel(self, shape):
        """
        Add a label to the label list and ensure it's unique.
       # Construct the instance-specific label text
       """
        label_text = f"{shape.label} - ID: {shape.shape_id}"  # Label with ID

        # Maintain a dictionary to track existing labels for fast lookup
        if not hasattr(self, "labelSet"):
            self.labelSet = set()

        # Check if the label already exists
        if label_text in self.labelSet:
            return  # Avoid adding duplicates
        self.labelSet.add(label_text)  # Add to the set

        # Add the label to the LabelListWidget
        label_list_item = LabelListWidgetItem(label_text, shape)
        self.labelList.addItem(label_list_item)

        # Ensure the label is added to the Unique Label List (track the base label)
        if self.uniqLabelList.findItemByLabel(shape.label) is None:
            uniq_item = self.uniqLabelList.createItemFromLabel(shape.label)
            self.uniqLabelList.addItem(uniq_item)
            rgb = self._get_rgb_by_label(shape.label)  # Generate label-specific color
            self.uniqLabelList.setItemLabel(uniq_item, shape.label, rgb)

        # Add label to the label dialog history
        self.labelDialog.addLabelHistory(shape.label)

        # Enable actions related to shapes
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)
            
            # Update the shape's color and add a visual indicator in the label
        self._update_shape_color(shape)
        label_list_item.setForeground(QBrush(QColor(shape.fill_color)))  # Set text color
        label_list_item.setText(f'{label_text} ●')  # Add an indicator for the color






    def _update_shape_color(self, shape):
        r, g, b = self._get_rgb_by_label(shape.label)
        shape.line_color = QtGui.QColor(r, g, b)
        shape.vertex_fill_color = QtGui.QColor(r, g, b)
        shape.hvertex_fill_color = QtGui.QColor(255, 255, 255)
        shape.fill_color = QtGui.QColor(r, g, b, 128)
        shape.select_line_color = QtGui.QColor(255, 255, 255)
        shape.select_fill_color = QtGui.QColor(r, g, b, 155)

    def _get_rgb_by_label(self, label):
        if self._config["shape_color"] == "auto":
            item = self.uniqLabelList.findItemByLabel(label)
            if item is None:
                item = self.uniqLabelList.createItemFromLabel(label)
                self.uniqLabelList.addItem(item)
                rgb = self._get_rgb_by_label(label)
                self.uniqLabelList.setItemLabel(item, label, rgb)
            label_id = self.uniqLabelList.indexFromItem(item).row() + 1
            label_id += self._config["shift_auto_shape_color"]
            return LABEL_COLORMAP[label_id % len(LABEL_COLORMAP)]
        elif (
            self._config["shape_color"] == "manual"
            and self._config["label_colors"]
            and label in self._config["label_colors"]
        ):
            return self._config["label_colors"][label]
        elif self._config["default_shape_color"]:
            return self._config["default_shape_color"]
        return (0, 255, 0)

    def remLabels(self, shapes):
        for shape in shapes:
            item = self.labelList.findItemByShape(shape)
            self.labelList.removeItem(item)

    def loadShapes(self, shapes, replace=True):
        self._noSelectionSlot = True
        for shape in shapes:
            self.addLabel(shape)
        self.labelList.clearSelection()
        self._noSelectionSlot = False
        self.canvas.loadShapes(shapes, replace=replace)

    def loadLabels(self, shapes):
        s = []
        for shape in shapes:
            label = shape["label"]
            points = shape["points"]
            shape_type = shape["shape_type"]
            flags = shape["flags"]
            description = shape.get("description", "")
            group_id = shape["group_id"]
            other_data = shape["other_data"]

            if not points:
                # skip point-empty shape
                continue

            shape = Shape(
                label=label,
                shape_type=shape_type,
                group_id=group_id,
                description=description,
                mask=shape["mask"],
            )
            for x, y in points:
                shape.addPoint(QtCore.QPointF(x, y))
            shape.close()

            default_flags = {}
            if self._config["label_flags"]:
                for pattern, keys in self._config["label_flags"].items():
                    if re.match(pattern, label):
                        for key in keys:
                            default_flags[key] = False
            shape.flags = default_flags
            shape.flags.update(flags)
            shape.other_data = other_data

            s.append(shape)
        self.loadShapes(s)

    def loadFlags(self, flags):
        self.flag_widget.clear()
        for key, flag in flags.items():
            item = QtWidgets.QListWidgetItem(key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if flag else Qt.Unchecked)
            self.flag_widget.addItem(item)

    def saveLabels(self, filename):
        lf = LabelFile()

        def format_shape(s):
            data = s.other_data.copy()
            data.update(
                dict(
                    label=s.label.encode("utf-8") if PY3 else s.label,
                    points=[(p.x(), p.y()) for p in s.points],
                    group_id=s.group_id,
                    description=s.description,
                    shape_type=s.shape_type,
                    flags=s.flags,
                    mask=None
                    if s.mask is None
                    else utils.img_arr_to_b64(s.mask.astype(np.uint8)),
                )
            )
            return data

        shapes = [format_shape(item.shape()) for item in self.labelList]
        flags = {}
        for i in range(self.flag_widget.count()):
            item = self.flag_widget.item(i)
            key = item.text()
            flag = item.checkState() == Qt.Checked
            flags[key] = flag
        try:
            imagePath = osp.relpath(self.imagePath, osp.dirname(filename))
            imageData = self.imageData if self._config["store_data"] else None
            if osp.dirname(filename) and not osp.exists(osp.dirname(filename)):
                os.makedirs(osp.dirname(filename))
            lf.save(
                filename=filename,
                shapes=shapes,
                imagePath=imagePath,
                imageData=imageData,
                imageHeight=self.image.height(),
                imageWidth=self.image.width(),
                otherData=self.otherData,
                flags=flags,
            )
            self.labelFile = lf
            items = self.fileListWidget.findItems(self.imagePath, Qt.MatchExactly)
            if len(items) > 0:
                if len(items) != 1:
                    raise RuntimeError("There are duplicate files.")
                items[0].setCheckState(Qt.Checked)
            # disable allows next and previous image to proceed
            # self.filename = filename
            return True
        except LabelFileError as e:
            self.errorMessage(
                self.tr("Error saving label data"), self.tr("<b>%s</b>") % e
            )
            return False

    def duplicateSelectedShape(self):
        added_shapes = self.canvas.duplicateSelectedShapes()
        for shape in added_shapes:
            self.addLabel(shape)
        self.setDirty()

    def pasteSelectedShape(self):
        self.loadShapes(self._copied_shapes, replace=False)
        self.setDirty()

    def copySelectedShape(self):
        self._copied_shapes = [s.copy() for s in self.canvas.selectedShapes]
        self.actions.paste.setEnabled(len(self._copied_shapes) > 0)

    def labelSelectionChanged(self):
        if self._noSelectionSlot:
            return
        if self.canvas.editing():
            selected_shapes = []
            for item in self.labelList.selectedItems():
                selected_shapes.append(item.shape())
            if selected_shapes:
                self.canvas.selectShapes(selected_shapes)
            else:
                self.canvas.deSelectShape()

    def labelItemChanged(self, item):
        """Handle changes in the label list item (e.g., visibility or selection)."""
        # Get the associated shape object
        shape = item.shape()

        # Ensure the shape exists
        if not shape:
            print("Warning: No shape associated with this item.")
            return

        # Update visibility based on check state
        is_visible = item.checkState() == QtCore.Qt.CheckState.Checked
        self.canvas.setShapeVisible(shape, is_visible)

        # Handle item selection (click or confirmation action)
        if self.labelList.selectedItems() and item in self.labelList.selectedItems():
            # Deselect all shapes and select the current one
            self.canvas.deselectAllShapes()  # Deselect all shapes
            shape.selected = True  # Mark the current shape as selected
            self.canvas.selectedShapes = [shape]  # Update the selectedShapes list
            self.canvas.update()  # Refresh the canvas to reflect changes

            # Optional: Center the canvas view on the selected shape
            if hasattr(self.canvas, "centerOnShape"):
                self.canvas.centerOnShape(shape)

            # Optional: Provide visual feedback (e.g., change color to highlight)
            if hasattr(self.canvas, "highlightShape"):
                self.canvas.highlightShape(shape)

            # Log or confirm the action (e.g., print or show a confirmation dialog)
            print(f"Person ID {shape.shape_id} selected.")

            # Display a dialog to confirm the selected person
            response = QtWidgets.QMessageBox.question(
                self,
                "Confirm Selection",
                f"Do you confirm Person ID {shape.shape_id}?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if response == QtWidgets.QMessageBox.Yes:
                print(f"Person ID {shape.shape_id} confirmed.")
            else:
                print(f"Person ID {shape.shape_id} not confirmed.")

        # Update the canvas to reflect changes
        self.canvas.update()



    def labelOrderChanged(self):
        self.setDirty()
        self.canvas.loadShapes([item.shape() for item in self.labelList])

    # Callback functions:

    def newShape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        items = self.uniqLabelList.selectedItems()
        text = None
        if items:
            text = items[0].data(Qt.UserRole)
        flags = {}
        group_id = None
        description = ""
        if self._config["display_label_popup"] or not text:
            previous_text = self.labelDialog.edit.text()
            text, flags, group_id, description = self.labelDialog.popUp(text)
            if not text:
                self.labelDialog.edit.setText(previous_text)

        if text and not self.validateLabel(text):
            self.errorMessage(
                self.tr("Invalid label"),
                self.tr("Invalid label '{}' with validation type '{}'").format(
                    text, self._config["validate_label"]
                ),
            )
            text = ""
        if text:
            self.labelList.clearSelection()
            shape = self.canvas.setLastLabel(text, flags)
            shape.group_id = group_id
            shape.description = description
            self.addLabel(shape)
            self.actions.editMode.setEnabled(True)
            self.actions.undoLastPoint.setEnabled(False)
            self.actions.undo.setEnabled(True)
            self.setDirty()
        else:
            self.canvas.undoLastLine()
            self.canvas.shapesBackups.pop()

    def scrollRequest(self, delta, orientation):
        units = -delta * 0.1  # natural scroll
        bar = self.scrollBars[orientation]
        value = bar.value() + bar.singleStep() * units
        self.setScroll(orientation, value)

    def setScroll(self, orientation, value):
        self.scrollBars[orientation].setValue(int(value))
        self.scroll_values[orientation][self.filename] = value

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)
        self.zoom_values[self.filename] = (self.zoomMode, value)

    def addZoom(self, increment=1.1):
        zoom_value = self.zoomWidget.value() * increment
        if increment > 1:
            zoom_value = math.ceil(zoom_value)
        else:
            zoom_value = math.floor(zoom_value)
        self.setZoom(zoom_value)

    def zoomRequest(self, delta, pos):
        canvas_width_old = self.canvas.width()
        units = 1.1
        if delta < 0:
            units = 0.9
        self.addZoom(units)

        canvas_width_new = self.canvas.width()
        if canvas_width_old != canvas_width_new:
            canvas_scale_factor = canvas_width_new / canvas_width_old

            x_shift = round(pos.x() * canvas_scale_factor) - pos.x()
            y_shift = round(pos.y() * canvas_scale_factor) - pos.y()

            self.setScroll(
                Qt.Horizontal,
                self.scrollBars[Qt.Horizontal].value() + x_shift,
            )
            self.setScroll(
                Qt.Vertical,
                self.scrollBars[Qt.Vertical].value() + y_shift,
            )

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def enableKeepPrevScale(self, enabled):
        self._config["keep_prev_scale"] = enabled
        self.actions.keepPrevScale.setChecked(enabled)

    def onNewBrightnessContrast(self, qimage):
        self.canvas.loadPixmap(QtGui.QPixmap.fromImage(qimage), clear_shapes=False)

    def brightnessContrast(self, value):
        dialog = BrightnessContrastDialog(
            utils.img_data_to_pil(self.imageData),
            self.onNewBrightnessContrast,
            parent=self,
        )
        brightness, contrast = self.brightnessContrast_values.get(
            self.filename, (None, None)
        )
        if brightness is not None:
            dialog.slider_brightness.setValue(brightness)
        if contrast is not None:
            dialog.slider_contrast.setValue(contrast)
        dialog.exec_()

        brightness = dialog.slider_brightness.value()
        contrast = dialog.slider_contrast.value()
        self.brightnessContrast_values[self.filename] = (brightness, contrast)

    def togglePolygons(self, value):
        flag = value
        for item in self.labelList:
            if value is None:
                flag = item.checkState() == Qt.Unchecked
            item.setCheckState(Qt.Checked if flag else Qt.Unchecked)

    def loadFile(self, filename=None):
        """Load the specified file, or the last opened file if None."""
        # changing fileListWidget loads file
        if filename in self.imageList and (
            self.fileListWidget.currentRow() != self.imageList.index(filename)
        ):
            self.fileListWidget.setCurrentRow(self.imageList.index(filename))
            self.fileListWidget.repaint()
            return

        self.resetState()
        self.canvas.setEnabled(False)
        if filename is None:
            filename = self.settings.value("filename", "")
        filename = str(filename)
        if not QtCore.QFile.exists(filename):
            self.errorMessage(
                self.tr("Error opening file"),
                self.tr("No such file: <b>%s</b>") % filename,
            )
            return False
        # assumes same name, but json extension
        self.status(str(self.tr("Loading %s...")) % osp.basename(str(filename)))
        label_file = osp.splitext(filename)[0] + ".json"
        if self.output_dir:
            label_file_without_path = osp.basename(label_file)
            label_file = osp.join(self.output_dir, label_file_without_path)
        if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(label_file):
            try:
                self.labelFile = LabelFile(label_file)
            except LabelFileError as e:
                self.errorMessage(
                    self.tr("Error opening file"),
                    self.tr(
                        "<p><b>%s</b></p>"
                        "<p>Make sure <i>%s</i> is a valid label file."
                    )
                    % (e, label_file),
                )
                self.status(self.tr("Error reading %s") % label_file)
                return False
            self.imageData = self.labelFile.imageData
            self.imagePath = osp.join(
                osp.dirname(label_file),
                self.labelFile.imagePath,
            )
            self.otherData = self.labelFile.otherData
        else:
            self.imageData = LabelFile.load_image_file(filename)
            if self.imageData:
                self.imagePath = filename
            self.labelFile = None
        image = QtGui.QImage.fromData(self.imageData)

        if image.isNull():
            formats = [
                "*.{}".format(fmt.data().decode())
                for fmt in QtGui.QImageReader.supportedImageFormats()
            ]
            self.errorMessage(
                self.tr("Error opening file"),
                self.tr(
                    "<p>Make sure <i>{0}</i> is a valid image file.<br/>"
                    "Supported image formats: {1}</p>"
                ).format(filename, ",".join(formats)),
            )
            self.status(self.tr("Error reading %s") % filename)
            return False
        self.image = image
        self.filename = filename
        if self._config["keep_prev"]:
            prev_shapes = self.canvas.shapes
        self.canvas.loadPixmap(QtGui.QPixmap.fromImage(image))
        flags = {k: False for k in self._config["flags"] or []}
        if self.labelFile:
            self.loadLabels(self.labelFile.shapes)
            if self.labelFile.flags is not None:
                flags.update(self.labelFile.flags)
        self.loadFlags(flags)
        if self._config["keep_prev"] and self.noShapes():
            self.loadShapes(prev_shapes, replace=False)
            self.setDirty()
        else:
            self.setClean()
        self.canvas.setEnabled(True)
        # set zoom values
        is_initial_load = not self.zoom_values
        if self.filename in self.zoom_values:
            self.zoomMode = self.zoom_values[self.filename][0]
            self.setZoom(self.zoom_values[self.filename][1])
        elif is_initial_load or not self._config["keep_prev_scale"]:
            self.adjustScale(initial=True)
        # set scroll values
        for orientation in self.scroll_values:
            if self.filename in self.scroll_values[orientation]:
                self.setScroll(
                    orientation, self.scroll_values[orientation][self.filename]
                )
        # set brightness contrast values
        dialog = BrightnessContrastDialog(
            utils.img_data_to_pil(self.imageData),
            self.onNewBrightnessContrast,
            parent=self,
        )
        brightness, contrast = self.brightnessContrast_values.get(
            self.filename, (None, None)
        )
        if self._config["keep_prev_brightness"] and self.recentFiles:
            brightness, _ = self.brightnessContrast_values.get(
                self.recentFiles[0], (None, None)
            )
        if self._config["keep_prev_contrast"] and self.recentFiles:
            _, contrast = self.brightnessContrast_values.get(
                self.recentFiles[0], (None, None)
            )
        if brightness is not None:
            dialog.slider_brightness.setValue(brightness)
        if contrast is not None:
            dialog.slider_contrast.setValue(contrast)
        self.brightnessContrast_values[self.filename] = (brightness, contrast)
        if brightness is not None or contrast is not None:
            dialog.onNewValue(None)
        self.paintCanvas()
        self.addRecentFile(self.filename)
        self.toggleActions(True)
        self.canvas.setFocus()
        self.status(str(self.tr("Loaded %s")) % osp.basename(str(filename)))
        return True

    def resizeEvent(self, event):
        if (
            self.canvas
            and not self.image.isNull()
            and self.zoomMode != self.MANUAL_ZOOM
        ):
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        value = int(100 * value)
        self.zoomWidget.setValue(value)
        self.zoom_values[self.filename] = (self.zoomMode, value)

    def scaleFitWindow(self):
        """Figure out the size of the pixmap to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def enableSaveImageWithData(self, enabled):
        self._config["store_data"] = enabled
        self.actions.saveWithImageData.setChecked(enabled)

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        self.settings.setValue("filename", self.filename if self.filename else "")
        self.settings.setValue("window/size", self.size())
        self.settings.setValue("window/position", self.pos())
        self.settings.setValue("window/state", self.saveState())
        self.settings.setValue("recentFiles", self.recentFiles)
        # ask the use for where to save the labels
        # self.settings.setValue('window/geometry', self.saveGeometry())

    def dragEnterEvent(self, event):
        extensions = [
            ".%s" % fmt.data().decode().lower()
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]
        if event.mimeData().hasUrls():
            items = [i.toLocalFile() for i in event.mimeData().urls()]
            if any([i.lower().endswith(tuple(extensions)) for i in items]):
                event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not self.mayContinue():
            event.ignore()
            return
        items = [i.toLocalFile() for i in event.mimeData().urls()]
        self.importDroppedImageFiles(items)

    # User Dialogs #

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def openPrevImg(self, _value=False):
        keep_prev = self._config["keep_prev"]
        if QtWidgets.QApplication.keyboardModifiers() == (
            Qt.ControlModifier | Qt.ShiftModifier
        ):
            self._config["keep_prev"] = True

        if not self.mayContinue():
            return

        if len(self.imageList) <= 0:
            return

        if self.filename is None:
            return

        currIndex = self.imageList.index(self.filename)
        if currIndex - 1 >= 0:
            filename = self.imageList[currIndex - 1]
            if filename:
                self.loadFile(filename)

        self._config["keep_prev"] = keep_prev

    def openNextImg(self, _value=False, load=True):
        keep_prev = self._config["keep_prev"]
        if QtWidgets.QApplication.keyboardModifiers() == (
            Qt.ControlModifier | Qt.ShiftModifier
        ):
            self._config["keep_prev"] = True

        if not self.mayContinue():
            return

        if len(self.imageList) <= 0:
            return

        filename = None
        if self.filename is None:
            filename = self.imageList[0]
        else:
            currIndex = self.imageList.index(self.filename)
            if currIndex + 1 < len(self.imageList):
                filename = self.imageList[currIndex + 1]
            else:
                filename = self.imageList[-1]
        self.filename = filename

        if self.filename and load:
            self.loadFile(self.filename)

        self._config["keep_prev"] = keep_prev
        
    

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = osp.dirname(str(self.filename)) if self.filename else "."
        formats = [
            "*.{}".format(fmt.data().decode())
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]
        filters = self.tr("Image & Label files (%s)") % " ".join(
            formats + ["*%s" % LabelFile.suffix]
        )
        filters = self.tr("Image, Video,Label files (*.mp4 *.avi *.mov *.mkv *.jpg *.png *.json)")
        fileDialog = FileDialogPreview(self)
        fileDialog.setFileMode(FileDialogPreview.ExistingFile)
        fileDialog.setNameFilter(filters)
        fileDialog.setWindowTitle(
            self.tr("%s - Choose Image ,Video or Label file") % __appname__,
        )
        fileDialog.setWindowFilePath(path)
        fileDialog.setViewMode(FileDialogPreview.Detail)
        
        if fileDialog.exec_():
            fileName = fileDialog.selectedFiles()[0]
            if fileName.endswith(('.mp4', '.avi', '.mov', '.mkv')):  # Video formats
                    self.loadVideo(fileName)
            else:
                    self.loadFile(fileName)
            # Enable the frame navigation buttons only if the video is loaded successfully
        if self.video_capture.isOpened():
            self.actions.openPrevFrame.setEnabled(True)
            self.actions.openNextFrame.setEnabled(True)
    
    def load_models(self):
        """Load YOLO and FastReID models."""
        # Load YOLOv8 model (e.g., pretrained on COCO)
        self.yolo_model = YOLO("yolov8n.pt")  # Adjust YOLO model variant as needed

        # Load FastReID model
        cfg = get_cfg()
        cfg.merge_from_file("A:/data/Project-Skills/Labeling_tool-enchancement/labelme/fastreid/fast-reid\configs/Market1501/bagtricks_R50.yml")
        cfg.MODEL.WEIGHTS = "A:/data/Project-Skills/Labeling_tool-enchancement/labelme/market_bot_R50.pth"  # Path to trained FastReID weights
        cfg.MODEL.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        self.fastreid_model = DefaultPredictor(cfg)
        test_img = torch.randn(1, 3, 128, 256)  # Replace with appropriate input size
        feature = self.fastreid_model(test_img)
        print(feature.shape)  # Should output (1, expected_embedding_size) 
        
        # Initialize DeepSORT
        self.deepsort = DeepSort(max_age=50, n_init=3)
    
    def openVideo(self):
        """Open a video file for annotation."""
        options = QtWidgets.QFileDialog.Options()
        filePath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Video File", "", "Video Files (*.mp4 *.avi *.mov);;All Files (*)", options=options
        )
        if filePath:
            self.loadVideo(filePath)
            # Enable the frame navigation buttons only if the video is loaded successfully
            
        if self.playVideoButton is not None:
            self.playVideoButton.setEnabled(True)
        
        if self.video_capture.isOpened():
            self.actions.openPrevFrame.setEnabled(True)
            self.actions.openNextFrame.setEnabled(True)
            self.actions.AnnotateVideo.setEnabled(True)
    
    def loadVideo(self, video_path):
        """Loads the video file and initializes video processing."""
        self.video_capture = cv2.VideoCapture(video_path)
        
        if not self.video_capture.isOpened():
            self.errorMessage(self.tr("Error"), self.tr("Could notvideo"))
            return
        
        
        print("Video successfully loaded")
        print(f"Does playVideoButton exist? {hasattr(self, 'playVideoButton')}")
        # Successfully opened the video, set the flag
        self.is_video = True
        
        # Initialize frame information
        self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.current_frame = 0
        print("Video mode enabled")
        
        # Load the first frame to display
        self.loadFrame(self.current_frame)
        # Enable video navigation buttons#Vdeo Button
        # Enable the Play button
        # if hasattr(self, 'playVideoButton'):
        #     self.playVideoButton.setEnabled(True)
        # else:
        #     print("playVideoButton is not initialized or has been deleted")
        
        
        
        self.prevFrameButton.setEnabled(self.current_frame > 0)
        self.nextFrameButton.setEnabled(self.current_frame < self.total_frames - 1)
        
        # Connect buttons for frame navigation
        print("Video mode: Connecting video frame navigation buttons")
        self.prevFrameButton.clicked.connect(self.openPrevFrame)
        self.nextFrameButton.clicked.connect(self.openNextFrame)
        
        
        
        
        
    def loadFrame(self, frame_number):
        """Load a specific frame from the video."""
        if self.video_capture is None:
            print("Video capture object is None")
            return

        
        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        #actual_frame_number = self.video_capture.get(cv2.CAP_PROP_POS_FRAMES)
        #print(f"Requested frame: {frame_number}, Actual frame set by video capture: {actual_frame_number}")
        ret, frame = self.video_capture.read()
        print(f"Requested frame: {frame_number}, Successfully read frame: {ret}")
        
        if ret:
            # Convert the frame to QImage for display
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channel = rgb_frame.shape
            bytes_per_line = channel * width
            q_img = QtGui.QImage(rgb_frame.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
            self.image=q_img
            
            # Update the canvas
            if hasattr(self, 'canvas'):
                self.canvas.loadPixmap(QtGui.QPixmap.fromImage(q_img))
                self.current_frame = frame_number
                self.prevFrameButton.setEnabled(self.current_frame > 0)
                self.nextFrameButton.setEnabled(self.current_frame < self.total_frames - 1)
                self.setClean()
                self.canvas.update()
                self.repaint()
            else:
                self.errorMessage(self.tr("Error"), self.tr("Canvas not available to display frame"))
        else:
            self.errorMessage(self.tr("Error loading frame"), self.tr("Cannot load frame %d") % frame_number)

    
    def playVideo(self):
        """Play the loaded video frame by frame."""
        if not hasattr(self, 'video_capture') or not self.video_capture.isOpened():
            QtWidgets.QMessageBox.warning(self, "Error", "No video loaded.")
            return

        self.is_playing = True  # Set playback state to playing

        # Use QTimer to control the playback speed
        self.video_timer = QtCore.QTimer(self)
        self.video_timer.timeout.connect(self.playNextFrame)
        self.video_timer.start(33)  # Approx. 30 FPS (1000ms / 30fps = 33ms)
    
    
    
    def openNextFrame(self):
        """Go to the next frame."""
        if self.current_frame + 1 < self.total_frames:
            self.current_frame += 1
            self.loadFrame(self.current_frame)
               
    def openPrevFrame(self):
        """Go to the previous frame."""
        # print("Previous frame button clicked")
        if  self.current_frame - 1 >= 0:
            self.current_frame -= 1 # Decrement current frame number
            self.loadFrame(self.current_frame)

    def playNextFrame(self):
        """Play the next frame during video playback."""
        if self.is_playing and self.current_frame + 1 < self.total_frames:
            self.current_frame += 1
            self.loadFrame(self.current_frame)
        else:
            self.stopVideo()  # Stop playback if the end of the video is reached

    def stopVideo(self):
        """Stop video playback."""
        if hasattr(self, 'video_timer') and self.video_timer.isActive():
            self.video_timer.stop()
        self.is_playing = False
    
    def pauseVideo(self):
        """Pause video playback."""
        if hasattr(self, 'video_timer') and self.video_timer.isActive():
            self.video_timer.stop()
        self.is_playing = False

    def stopVideoPlayback(self):
        """Stop video playback and reset to the first frame."""
        self.pauseVideo()
        self.current_frame = 0
        self.loadFrame(self.current_frame)

    
        
    def preprocess_image(self, img):
        """Preprocess image for FastReID input."""
        img = cv2.resize(img, (128, 256))
        img = img / 255.0  # Normalize to [0, 1]
        img = torch.tensor(img).permute(2, 0, 1).unsqueeze(0).float()
        return img 
    
    





    
    # The new changes in the ReID which lead to the annotateVideo
    def is_same_person(feature1, feature2, threshold=0.5):
        """Compare two ReID feature vectors and return True if they match."""
        distance = euclidean(feature1, feature2)
        return distance < threshold  # Return True if within the threshold

    def get_random_color(self):
        """Generate a random color in the form of (R, G, B)"""
        color= (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        return color
    
    
    
    # def track_persons(self, frame):
    #     """Track persons and extract features."""
    #     results = self.yolo_model(frame)
    #     boxes = []
    #     features = []
        
    #     for det in results[0].boxes:
    #         if int(det.cls[0]) == 0:  # Class 0 is 'person'
    #             x1, y1, x2, y2 = map(int, det.xyxy[0].tolist())
    #             boxes.append((x1, y1, x2, y2))

    #             # Extract ReID features
    #             feature = self.extract_reid_features(frame, [(x1, y1, x2, y2)])
    #             features.append((feature[0][0], (x1, y1, x2, y2)))  # Pack feature and bounding box as a tuple
        
    #     print(f"Features with bounding boxes: {features}")  # Print for debugging
    #     return boxes, features



    
    
    def extract_reid_features(self, frame, boxes):
        """Extract ReID features for detected persons."""
        features = []
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            cropped_img = frame[y1:y2, x1:x2]

            if cropped_img.size == 0:
                continue

            processed_img = self.preprocess_image(cropped_img)
            processed_img = processed_img.to(self.fastreid_model.model.device)

            with torch.no_grad():
                output = self.fastreid_model(processed_img)
                if isinstance(output, torch.Tensor):
                    feature = output.detach().cpu().numpy().flatten()
                elif isinstance(output, dict) and "feat" in output:
                    feature = output["feat"].detach().cpu().numpy().flatten()
                else:
                    raise ValueError("Unexpected output format from FastReID model.")

            # Ensure feature is flat and consistent
            features.append((feature, (x1, y1, x2, y2)))  # Tuple of (feature, bounding box)
        return features


    def match_ids(self, current_features, previous_features, threshold=0.7):
        """
        Match current features to previous features based on cosine similarity.
        
        Args:
            current_features: List of tuples [(feature_vector, bbox), ...].
            previous_features: List of tuples [(feature_vector, bbox), ...].
            threshold: Minimum cosine similarity to consider a match.
        
        Returns:
            List of tuples [(current_idx, matched_idx)].
        """
        matches = []
        used_ids=set()
        
        # print(f"Current Features: {current_features}")
        # print(f"Previous Features: {previous_features}")
        
        for i, (curr_feat, curr_bbox) in enumerate(current_features):
            # print(f"Processing current feature {i}: {curr_feat}, {curr_bbox}")
            
            best_match = -1
            best_similarity = threshold

            # Ensure the feature vector is a flat numpy array
            curr_feat = np.array(curr_feat).flatten()
            # print(f"Flattened current feature: {curr_feat}")

            for j, (prev_feat, prev_bbox) in enumerate(previous_features):
                prev_feat = np.array(prev_feat).flatten()
                # print(f"Flattened previous feature {j}: {prev_feat}")
                
                # Compute cosine similarity
                similarity = cosine_similarity([curr_feat], [prev_feat])[0][0]
                if similarity > best_similarity and j not in used_ids:
                    best_similarity = similarity
                    best_match = j

            if best_match == -1:
                # Assign a new ID if no match is found
                new_id = max(used_ids) + 1 if used_ids else 1
                matches.append((i, new_id))
                used_ids.add(new_id)
            else:
                # Reuse the matched ID
                matches.append((i, best_match))
                used_ids.add(best_match)

        return matches

    # Generate unique color for each track_id
    def get_color_for_id(self,track_id):
        """
        Generate or retrieve a unique color for a given ID.
        """
        random.seed(track_id)  # Seed the random generator with the ID for consistent colors
        return (
            random.randint(0, 255),  # Red
            random.randint(0, 255),  # Green
            random.randint(0, 255),  # Blue
        )
    
    

    



    def normalize_bbox(self, bbox):
        return tuple(map(int, bbox))

    def iou(self,box1, box2):
        x1, y1, x2, y2 = box1
        x1_, y1_, x2_, y2_ = box2

        inter_x1 = max(x1, x1_)
        inter_y1 = max(y1, y1_)
        inter_x2 = min(x2, x2_)
        inter_y2 = min(y2, y2_)
        inter_area = max(0, inter_x2 - inter_x1 + 1) * max(0, inter_y2 - inter_y1 + 1)

        box1_area = (x2 - x1 + 1) * (y2 - y1 + 1)
        box2_area = (x2_ - x1_ + 1) * (y2_ - y1_ + 1)
        union_area = box1_area + box2_area - inter_area

        return inter_area / union_area if union_area > 0 else 0

      # Should output (1, expected_embedding_size)

    
    
    def annotateVideo(self):
        
       
        """Annotate video with YOLO, FastReID, and DeepSORT."""
        self.load_models()

        frames = []
        all_annotations = []

        # Initialize the Tracker
        max_cosine_distance = 0.5
        max_age = 30
        n_init = 3
        metric = NearestNeighborDistanceMetric("cosine", max_cosine_distance, None)
        if not hasattr(self, 'tracker'):
            self.tracker = Tracker(metric=metric, max_age=max_age, n_init=n_init)

        person_colors = {}
        if not hasattr(self, 'track_id_manager'):
            self.track_id_manager = IDManager()

        # Set the expected embedding size (based on the model)
        if not hasattr(self, 'expected_embedding_size'):
            self.expected_embedding_size =2048   # Replace with your model's actual output size

        # Process the video frame by frame
        while self.video_capture.isOpened():
            ret, frame = self.video_capture.read()
            if not ret:
                print("End of video or no frame available.")
                break

            # Step 1: Run YOLO for person detection
            results = self.yolo_model(frame)
            boxes, confidences = [], []
            for det in results[0].boxes:
                if int(det.cls[0]) == 0 and float(det.conf[0]) > 0.5:  # Class 0 is person
                    x1, y1, x2, y2 = map(int, det.xyxy[0].tolist())
                    
                    boxes.append((x1, y1, x2, y2))
                    confidences.append(float(det.conf[0]))
                print(f"Raw YOLO output box: {det.xyxy[0].tolist()}")
            # Step 2: Extract ReID features for detected boxes
            current_features = self.extract_reid_features(frame, boxes)
            detections = []
            frame_height, frame_width, _ = frame.shape
            print(f"Frame dimensions: Width={frame_width}, Height={frame_height}")
            print(f"Bounding box: {boxes}")

            for box, confidence, feature in zip(boxes, confidences, current_features):
                if not (0 <= box[0] < box[2] <= frame_width and 0 <= box[1] < box[3] <= frame_height):
                    print(f"Skipping invalid YOLO bounding box: {box}")
                    continue
                
                if isinstance(feature, tuple):
                    feature = feature[0]  # Handle feature as tuple if needed
                try:
                    feature_vector = np.array(feature).flatten()
                    # Validate feature size
                    if len(feature_vector) != self.expected_embedding_size:
                        print(f"Skipping box {box}: Invalid feature size")
                        continue

                    # Validate and normalize bounding box
                    x1, y1, x2, y2 = box
                    if not (0 <= x1 < frame_width and 0 <= y1 < frame_height and 0 <= x2 <= frame_width and 0 <= y2 <= frame_height and x1 < x2 and y1 < y2):
                        print(f"Skipping invalid bounding box: {box}")
                        continue

                    bbox_tuple = (x1 / frame_width, y1 / frame_height, x2 / frame_width, y2 / frame_height)
                    detection = Detection(bbox_tuple, confidence, feature_vector)
                    detections.append(detection)
                except Exception as e:
                    print(f"Error preparing detection for box {box}: {e}")


                    # Step 3: Update the tracker
            # Step 3: Update the tracker
            if detections:
                try:
                    self.tracker.predict()
                    self.tracker.update(detections=detections)  # Pass the list of detections
                except Exception as e:
                    print(f"Error during tracker update: {e}")
            else:
                print("No valid detections for this frame, skipping tracker update.")



            
                    # Step 4: Process and annotate tracks
            frame_annotations = []
            for track in self.tracker.tracks:
                
                # Skip unconfirmed tracks or tracks that haven't been updated recently
                if not track.is_confirmed() or track.time_since_update > 1:
                    print(f"Unconfirmed track, skipping: {track}")
                    
                
                            # Assign a new ID if not already assigned
                if not hasattr(track, 'track_id') or track.track_id not in self.track_id_manager.used_ids:
                    track.track_id = self.track_id_manager.get_new_id()
                    continue
                # Get track ID and bounding box
                # track_id = track.track_id
                bbox = track.to_tlbr()  # Bounding box in (x1, y1, x2, y2) format
                print(f"Track ID: {track.track_id}, Bounding box: {track.to_tlbr()}")
                
                 # Validate bounding box dimensions
                if not (0 <= bbox[0] < bbox[2] <= frame_width and 0 <= bbox[1] < bbox[3] <= frame_height):
                    print(f"Invalid bounding box for track ID {track.track_id}: {bbox}")
                    continue

                            # Release ID for terminated tracks
                if not track.is_confirmed() and track.time_since_update > self.tracker.max_age:
                    print(f"Track already has ID: {track.track_id}")
                    print(f"Releasing Track ID: {track.track_id} due to inactivity.")
                    self.track_id_manager.release_id(track.track_id)
                    
                    continue
                # Assign unique colors to each track ID
                if track.track_id not in person_colors:
                    person_colors[track.track_id] = self.get_random_color()
                color = person_colors[track.track_id]

                # Annotate the frame with bounding box and label
                label_text = f"Person ID: {track.track_id}"
                cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)
                cv2.putText(frame, label_text, (int(bbox[0]), int(bbox[1]) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # # Match detection for confidence (optional, depending on detection-tracking pipeline)
                # matched_detection = None
                # for detection in detections:
                #     if self.iou(detection.to_tlbr(), bbox) > 0.3:  # IoU threshold
                #         matched_detection = detection
                #         break
                # detection_confidence = matched_detection.confidence if matched_detection else "No detection"
                for detection in detections:
                    if detection.confidence < 0.5:  # Example confidence threshold
                        continue
                    
                # Debugging output
                print(f"Track ID: {track.track_id}, BBox: {bbox}, Confidence: {confidence}")

                # Create a Shape object for LabelMe annotation
                shape = Shape(label=f"person{track.track_id}", shape_id=track.track_id)
                shape.addPoint(QtCore.QPointF(bbox[0], bbox[1]))
                shape.addPoint(QtCore.QPointF(bbox[2], bbox[1]))
                shape.addPoint(QtCore.QPointF(bbox[2], bbox[3]))
                shape.addPoint(QtCore.QPointF(bbox[0], bbox[3]))
                self.addLabel(shape)

                # Update label lists
                self.labelList.addPersonLabel(track.track_id, color)  # Update Label List
                self.uniqLabelList.addUniquePersonLabel(f"person{track.track_id}", color)  # Update Unique Label List

                # Append annotations for the current frame
                frame_annotations.append({
                    "track_id": track.track_id,
                    "bbox": list(bbox),
                    "confidence": confidence,
                    "class": "person"
                })
                print(f"Track ID: {track.track_id}, BBox: {bbox}, Confidence: {confidence}")

            if frame_annotations:
                    all_annotations.append(frame_annotations)
            frames.append(frame)

                    # Update display
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channel = rgb_frame.shape
                bytes_per_line = channel * width
                q_img = QtGui.QImage(rgb_frame.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(q_img)
                self.canvas.loadPixmap(pixmap)
                self.canvas.update()
            except Exception as e:
                print(f"Error updating UI for frame: {e}")
        
        # Step 4: Ask the user for the desired annotation format
        format_choice = self.choose_annotation_format()
        if format_choice:
            self.save_reid_annotations(frames, all_annotations, format_choice)
            self.actions.saveReIDAnnotationsAction.setEnabled(True) 
        else:
            print("Annotation saving canceled by user.")
        self.video_capture.release()
        cv2.destroyAllWindows()




    def choose_annotation_format(self):
        """Allow the user to choose the annotation format."""
        formats = ["JSON", "XML", "COCO", "YOLO"]  # Add more formats if needed
        format_choice, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Choose Annotation Format",
            "Select the format for saving annotations:",
            formats,
            0,
            False,
        )
        if ok and format_choice:
            return format_choice.lower()
        return None

    
    
    

    def get_random_color(self):
        """Generate a random color for bounding boxes."""
        return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    
    def find_bbox_match(self, bbox, boxes, iou_threshold=0.5):
        """
        Find the best-matching bounding box for a given bbox using IoU.
        Args:
            bbox: The bounding box to match (x1, y1, x2, y2).
            boxes: List of detected boxes [(x1, y1, x2, y2), ...].
            iou_threshold: Minimum IoU threshold to consider a match.
        Returns:
            The best-matching box from `boxes`, or None if no match is found.
        """
        def iou(box1, box2):
            x1, y1, x2, y2 = box1
            x1_, y1_, x2_, y2_ = box2

            # Compute intersection
            inter_x1 = max(x1, x1_)
            inter_y1 = max(y1, y1_)
            inter_x2 = min(x2, x2_)
            inter_y2 = min(y2, y2_)
            inter_area = max(0, inter_x2 - inter_x1 + 1) * max(0, inter_y2 - inter_y1 + 1)

            # Compute union
            box1_area = (x2 - x1 + 1) * (y2 - y1 + 1)
            box2_area = (x2_ - x1_ + 1) * (y2_ - y1_ + 1)
            union_area = box1_area + box2_area - inter_area

            return inter_area / union_area if union_area > 0 else 0

        best_match = None
        best_iou = 0

        for detected_box in boxes:
            current_iou = iou(bbox, detected_box)
            if current_iou > best_iou and current_iou >= iou_threshold:
                best_match = detected_box
                best_iou = current_iou

        return best_match




        
        
    def enable_save_annotation_button(self):
        """Enable the saveReIDAnnotation button after video annotation is done."""
        self.saveReIDAnnotationsAction.setEnabled(True)  # Enable the saveReIDAnnotation button
 
    
    def choose_annotation_format(self):
        """Allow the user to choose the annotation format."""
        formats = ["JSON", "XML", "COCO", "YOLO"]  # Add more formats if needed
        format_choice, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Choose Annotation Format",
            "Select the format for saving annotations:",
            formats,
            0,
            False,
        )
        if ok and format_choice:
            return format_choice.lower()
        return None

    
    
    
    
    
    
    def save_reid_annotations(self, frames, all_annotations, format_choice="json"):
        """Save the annotations in the chosen format."""
        options = QtWidgets.QFileDialog.Options()
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Annotations", "", f"{format_choice.upper()} Files (*.{format_choice});;All Files (*)", options=options
        )

        if not file_path:
            print("Save canceled by user.")
            return

        try:
            if format_choice == "json":
                with open(file_path, "w") as f:
                    json.dump(all_annotations, f, indent=4)
            elif format_choice == "xml":
                self.save_annotations_as_xml(file_path, all_annotations)
            elif format_choice == "coco":
                self.save_annotations_as_coco(file_path, all_annotations)
            elif format_choice == "yolo":
                self.save_annotations_as_yolo(file_path, all_annotations)
            else:
                raise ValueError(f"Unsupported format: {format_choice}")

            QtWidgets.QMessageBox.information(self, "Success", f"Annotations saved as {format_choice.upper()}!")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save annotations: {e}")
            print(f"Error saving annotations: {e}")



    def collect_reid_annotations(self, frames, all_annotations):
        """
        Collect the ReID annotations (bounding boxes, IDs, and confidences) for each frame.
        Each frame contains the following structure:
        - frame_index
        - detections: List of detected objects, each with track_id, bbox, confidence, class
        """
        annotations = []

        for frame_index, frame_annotations in enumerate(all_annotations):
            frame_data = {
                "frame": frame_index,
                "detections": []
            }

            for annotation in frame_annotations:
                # Validate the structure of each annotation
                if not isinstance(annotation, dict):
                    raise ValueError(f"Invalid annotation format at frame {frame_index}: {annotation}")

                # Ensure required keys exist
                required_keys = {"track_id", "bbox", "confidence", "class"}
                if not required_keys.issubset(annotation.keys()):
                    raise KeyError(f"Missing keys in annotation at frame {frame_index}: {annotation}")

                detection_data = {
                    "track_id": annotation["track_id"],
                    "bbox": annotation["bbox"],
                    "confidence": annotation["confidence"],
                    "class": annotation["class"]  # For example, "person"
                }
                frame_data["detections"].append(detection_data)

            annotations.append(frame_data)

        return annotations
    
    def save_annotations_as_coco(self,file_path, all_annotations):
        """Save annotations in COCO format."""
        # Convert annotations to COCO format
        coco_annotations = {
            "info": {"description": "Generated by LabelMe"},
            "images": [],
            "annotations": [],
            "categories": [{"id": 1, "name": "person"}],
        }
        for frame_idx, frame_anno in enumerate(all_annotations):
            coco_annotations["images"].append({"id": frame_idx, "file_name": f"frame_{frame_idx}.jpg"})
            for anno in frame_anno:
                coco_annotations["annotations"].append({
                    "id": anno["track_id"],
                    "image_id": frame_idx,
                    "bbox": anno["bbox"],
                    "category_id": 1,
                    "confidence": anno["confidence"]
                })
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save as COCO", "", "COCO Files (*.json)")
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(coco_annotations, f, indent=4)


    def save_annotations_as_xml(self,file_path, all_annotations):
        """Save annotations in Pascal VOC format."""
        for frame_idx, frame_anno in enumerate(all_annotations):
            root = Element('annotation')

            # Add the filename of the frame
            SubElement(root, 'filename').text = f"frame_{frame_idx}.jpg"

            # Loop through annotations for the current frame
            for anno in frame_anno:
                obj = SubElement(root, 'object')
                SubElement(obj, 'name').text = "person"  # Class name
                bndbox = SubElement(obj, 'bndbox')

                # Add bounding box coordinates
                SubElement(bndbox, 'xmin').text = str(anno["bbox"][0])
                SubElement(bndbox, 'ymin').text = str(anno["bbox"][1])
                SubElement(bndbox, 'xmax').text = str(anno["bbox"][2])
                SubElement(bndbox, 'ymax').text = str(anno["bbox"][3])

            # Save the XML file for the current frame
            tree = ElementTree(root)
            file_path = f"frame_{frame_idx}.xml"  # You can customize the file path if needed
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
            print(f"Saved Pascal VOC annotations to {file_path}")
            
    def save_annotations_as_yolo(self, file_path, all_annotations):
        """
        Save annotations in YOLO format.
        Each line in a YOLO annotation file represents an object and has the format:
        <class> <x_center> <y_center> <width> <height>
        where values are normalized to [0, 1].
        """
        try:
            frame_width = self.video_capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            frame_height = self.video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT)

            with open(file_path, 'w') as f:
                for frame_idx, frame_anno in enumerate(all_annotations):
                    for anno in frame_anno:
                        bbox = anno["bbox"]
                        x_center = ((bbox[0] + bbox[2]) / 2) / frame_width
                        y_center = ((bbox[1] + bbox[3]) / 2) / frame_height
                        width = (bbox[2] - bbox[0]) / frame_width
                        height = (bbox[3] - bbox[1]) / frame_height

                        # Write in YOLO format: <class> <x_center> <y_center> <width> <height>
                        f.write(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")

            print(f"YOLO annotations saved to {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save YOLO annotations: {e}")
            print(f"Error saving YOLO annotations: {e}")



    

    

  
   
    
    

            
    
    
    def display_reid_detections(self, detections):
        """Display ReID detections on the frame."""
        for detection in detections:
            # Ensure detection has the required number of elements (e.g., [x1, y1, x2, y2, confidence, class_id])
            if isinstance(detection, torch.Tensor):
                # Convert to a list and ensure there are at least 4 elements
                detection_list = detection.tolist()
                if len(detection_list) >= 4:
                    # Assuming YOLO returns [x1, y1, x2, y2, confidence, class_id]
                    x1, y1, x2, y2 = map(int, detection_list[:4])
                else:
                    # If not enough values, skip this detection
                    continue
            elif isinstance(detection, dict) and 'bbox' in detection:
                x1, y1, x2, y2 = map(int, detection['bbox'])
            else:
                # Handle unexpected data types if needed
                continue

            # Draw the bounding box on the frame
            painter = QtGui.QPainter(self.canvas.pixmap())
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 255, 0), 2))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
            painter.end()

        self.canvas.update()  # Refresh the canvas to show updated annotations
  # Refresh the canvas to show updated annotations
            
    def update_display(self, frame):
        """Display the updated frame in the LabelMe UI."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channel = rgb_frame.shape
        bytes_per_line = 3 * width
        q_img = QtGui.QImage(rgb_frame.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(q_img)

        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.loadPixmap(pixmap)


    def closeVideo(self):
        """Release video resources."""
        if hasattr(self, 'video_capture') and self.video_capture.isOpened():
            self.video_capture.release()
        print("Video capture resources released.")  
        # Enable the frame navigation buttons only if the video is loaded successfully
        if self.video_capture.isOpened():
            self.actions.openPrevFrame.setEnabled(False)
            self.actions.openNextFrame.setEnabled(False) 
            self.actions.AnnotateVideo.setEnabled(False)

  



    
    
    def load_annotations(video_name):
        with open(f"{video_name}_annotations.json", "r") as f:
            annotations = json.load(f)
        return annotations


    def changeOutputDirDialog(self, _value=False):
        default_output_dir = self.output_dir
        if default_output_dir is None and self.filename:
            default_output_dir = osp.dirname(self.filename)
        if default_output_dir is None:
            default_output_dir = self.currentPath()

        output_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("%s - Save/Load Annotations in Directory") % __appname__,
            default_output_dir,
            QtWidgets.QFileDialog.ShowDirsOnly
            | QtWidgets.QFileDialog.DontResolveSymlinks,
        )
        output_dir = str(output_dir)

        if not output_dir:
            return

        self.output_dir = output_dir

        self.statusBar().showMessage(
            self.tr("%s . Annotations will be saved/loaded in %s")
            % ("Change Annotations Dir", self.output_dir)
        )
        self.statusBar().show()

        current_filename = self.filename
        self.importDirImages(self.lastOpenDir, load=False)

        if current_filename in self.imageList:
            # retain currently selected file
            self.fileListWidget.setCurrentRow(self.imageList.index(current_filename))
            self.fileListWidget.repaint()

    def saveFile(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        if self.labelFile:
            # DL20180323 - overwrite when in directory
            self._saveFile(self.labelFile.filename)
        elif self.output_file:
            self._saveFile(self.output_file)
            self.close()
        else:
            self._saveFile(self.saveFileDialog())

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._saveFile(self.saveFileDialog())

    def saveFileDialog(self):
        caption = self.tr("%s - Choose File") % __appname__
        filters = self.tr("Label files (*%s)") % LabelFile.suffix
        if self.output_dir:
            dlg = QtWidgets.QFileDialog(self, caption, self.output_dir, filters)
        else:
            dlg = QtWidgets.QFileDialog(self, caption, self.currentPath(), filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dlg.setOption(QtWidgets.QFileDialog.DontConfirmOverwrite, False)
        dlg.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, False)
        basename = osp.basename(osp.splitext(self.filename)[0])
        if self.output_dir:
            default_labelfile_name = osp.join(
                self.output_dir, basename + LabelFile.suffix
            )
        else:
            default_labelfile_name = osp.join(
                self.currentPath(), basename + LabelFile.suffix
            )
        filename = dlg.getSaveFileName(
            self,
            self.tr("Choose File"),
            default_labelfile_name,
            self.tr("Label files (*%s)") % LabelFile.suffix,
        )
        if isinstance(filename, tuple):
            filename, _ = filename
        return filename

    def _saveFile(self, filename):
        if filename and self.saveLabels(filename):
            self.addRecentFile(filename)
            self.setClean()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def getLabelFile(self):
        if self.filename.lower().endswith(".json"):
            label_file = self.filename
        else:
            label_file = osp.splitext(self.filename)[0] + ".json"

        return label_file

    def deleteFile(self):
        mb = QtWidgets.QMessageBox
        msg = self.tr(
            "You are about to permanently delete this label file, " "proceed anyway?"
        )
        answer = mb.warning(self, self.tr("Attention"), msg, mb.Yes | mb.No)
        if answer != mb.Yes:
            return

        label_file = self.getLabelFile()
        if osp.exists(label_file):
            os.remove(label_file)
            logger.info("Label file is removed: {}".format(label_file))

            item = self.fileListWidget.currentItem()
            item.setCheckState(Qt.Unchecked)

            self.resetState()

    # Message Dialogs. #
    def hasLabels(self):
        if self.noShapes():
            self.errorMessage(
                "No objects labeled",
                "You must label at least one object to save the file.",
            )
            return False
        return True

    def hasLabelFile(self):
        if self.filename is None:
            return False

        label_file = self.getLabelFile()
        return osp.exists(label_file)

    def mayContinue(self):
        if not self.dirty:
            return True
        mb = QtWidgets.QMessageBox
        msg = self.tr('Save annotations to "{}" before closing?').format(self.filename)
        answer = mb.question(
            self,
            self.tr("Save annotations?"),
            msg,
            mb.Save | mb.Discard | mb.Cancel,
            mb.Save,
        )
        if answer == mb.Discard:
            return True
        elif answer == mb.Save:
            self.saveFile()
            return True
        else:  # answer == mb.Cancel
            return False

    def errorMessage(self, title, message):
        return QtWidgets.QMessageBox.critical(
            self, title, "<p><b>%s</b></p>%s" % (title, message)
        )

    def currentPath(self):
        return osp.dirname(str(self.filename)) if self.filename else "."

    def toggleKeepPrevMode(self):
        self._config["keep_prev"] = not self._config["keep_prev"]

    def removeSelectedPoint(self):
        self.canvas.removeSelectedPoint()
        self.canvas.update()
        if not self.canvas.hShape.points:
            self.canvas.deleteShape(self.canvas.hShape)
            self.remLabels([self.canvas.hShape])
            if self.noShapes():
                for action in self.actions.onShapesPresent:
                    action.setEnabled(False)
        self.setDirty()

    def deleteSelectedShape(self):
        yes, no = QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No
        msg = self.tr(
            "You are about to permanently delete {} polygons, " "proceed anyway?"
        ).format(len(self.canvas.selectedShapes))
        if yes == QtWidgets.QMessageBox.warning(
            self, self.tr("Attention"), msg, yes | no, yes
        ):
            self.remLabels(self.canvas.deleteSelected())
            self.setDirty()
            if self.noShapes():
                for action in self.actions.onShapesPresent:
                    action.setEnabled(False)

    def copyShape(self):
        self.canvas.endMove(copy=True)
        for shape in self.canvas.selectedShapes:
            self.addLabel(shape)
        self.labelList.clearSelection()
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def openDirDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else "."
        if self.lastOpenDir and osp.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = osp.dirname(self.filename) if self.filename else "."

        targetDirPath = str(
            QtWidgets.QFileDialog.getExistingDirectory(
                self,
                self.tr("%s - Open Directory") % __appname__,
                defaultOpenDirPath,
                QtWidgets.QFileDialog.ShowDirsOnly
                | QtWidgets.QFileDialog.DontResolveSymlinks,
            )
        )
        self.importDirImages(targetDirPath)

    @property
    def imageList(self):
        lst = []
        for i in range(self.fileListWidget.count()):
            item = self.fileListWidget.item(i)
            lst.append(item.text())
        return lst

    def importDroppedImageFiles(self, imageFiles):
        extensions = [
            ".%s" % fmt.data().decode().lower()
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]

        self.filename = None
        for file in imageFiles:
            if file in self.imageList or not file.lower().endswith(tuple(extensions)):
                continue
            label_file = osp.splitext(file)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = osp.join(self.output_dir, label_file_without_path)
            item = QtWidgets.QListWidgetItem(file)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(label_file):
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.fileListWidget.addItem(item)

        if len(self.imageList) > 1:
            self.actions.openNextImg.setEnabled(True)
            self.actions.openPrevImg.setEnabled(True)

        self.openNextImg()

    def importDirImages(self, dirpath, pattern=None, load=True):
        self.actions.openNextImg.setEnabled(True)
        self.actions.openPrevImg.setEnabled(True)

        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.filename = None
        self.fileListWidget.clear()

        filenames = self.scanAllImages(dirpath)
        if pattern:
            try:
                filenames = [f for f in filenames if re.search(pattern, f)]
            except re.error:
                pass
        for filename in filenames:
            label_file = osp.splitext(filename)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = osp.join(self.output_dir, label_file_without_path)
            item = QtWidgets.QListWidgetItem(filename)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(label_file):
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.fileListWidget.addItem(item)
        self.openNextImg(load=load)

    def scanAllImages(self, folderPath):
        extensions = [
            ".%s" % fmt.data().decode().lower()
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]

        images = []
        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.normpath(osp.join(root, file))
                    images.append(relativePath)
        images = natsort.os_sorted(images)
        return images

# def get_transform(self):
#         """Create a transformation pipeline for person ReID model input."""
#         return transforms.Compose([
#             transforms.ToPILImage(),                # Convert from NumPy array to PIL image
#             transforms.Resize((128, 256)),          # Resize to a standard size suitable for the model
#             transforms.ToTensor(),                  # Convert PIL image to Tensor
#             transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])  # Standard normalization
#         ])


class IDManager:
   
    def __init__(self):
        self.used_ids = set()
        self.next_id = 1

    def get_new_id(self):
        while self.next_id in self.used_ids:
            self.next_id += 1
        new_id = self.next_id
        self.used_ids.add(new_id)
        return new_id

    def release_id(self, track_id):
        if track_id in self.used_ids:
            self.used_ids.remove(track_id)