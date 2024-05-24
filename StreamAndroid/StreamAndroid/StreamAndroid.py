import time

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

try:
  import scrcpy
except ModuleNotFoundError:
  slicer.util.pip_install("scrcpy")
  import scrcpy

try:
  from adbutils import adb
except ModuleNotFoundError:
  slicer.util.pip_install("adbutils")
  from adbutils import adb

try:
  import cv2
except ModuleNotFoundError:
  slicer.util.pip_install("opencv-python")
  import cv2


#
# StreamAndroid
#

class StreamAndroid(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Stream Android"  # TODO: make this more human readable by adding spaces
        self.parent.categories = ["Utilities"]  # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Colton Barr (Perk Lab / BWH)"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        self.parent.helpText = ""
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
"""

#
# StreamAndroidWidget
#

class StreamAndroidWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._updatingGUIFromParameterNode = False

    def setup(self):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/StreamAndroid.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = StreamAndroidLogic()

        # Connections

        # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
        # (in the selected parameter node).
        self.ui.startStreamingButton.connect('clicked(bool)', self.onStartStreamingButton)
        self.ui.stopStreamingButton.connect('clicked(bool)', self.onStopStreamingButton)
        self.ui.refreshDeviceListButton.connect('clicked(bool)', self.updateDeviceComboBox)

        self.ui.outputVolumeComboBox.setMRMLScene(slicer.mrmlScene)

        #Set initial UI conditions
        self.updateDeviceComboBox()
        self.notStreamingUIState()

    def updateUIState(self):
        self.notStreamingUIState()

    def updateDeviceComboBox(self):
        deviceList = adb.device_list()
        self.ui.deviceComboBox.clear()
        for device in deviceList:
            self.ui.deviceComboBox.addItem(device.info['serialno'])

    def streamingUIState(self):
        self.ui.configCollapsibleButton.enabled = False
        self.ui.startStreamingButton.enabled = False
        self.ui.stopStreamingButton.enabled = True

    def notStreamingUIState(self):
        self.ui.configCollapsibleButton.enabled = True
        self.ui.stopStreamingButton.enabled = False
        self.ui.startStreamingButton.enabled = True

    def onStartStreamingButton(self):

        self.streamingUIState()

        config = {'clientIndex'  : self.ui.deviceComboBox.currentIndex,
                  'outputVolume' : self.ui.outputVolumeComboBox.currentNode(),
                  'bitrate'      : self.ui.bitrateSpinBox.value,
                  'fpsSpinBox'   : self.ui.fpsSpinBox.value,
                  'maxWidth'     : self.ui.maxWidthSpinBox.value,
                  'flipImage'    : self.ui.flipImageCheckBox.checked,
                  'stayAwake'      : self.ui.stayAwakeCheckBox.checked}

        self.logic.startStreaming(config)

        self.streamingUIState()

    def onStopStreamingButton(self):

        self.logic.stopStreaming(self.ui.outputVolumeComboBox.currentNode())
        self.notStreamingUIState()
#
# StreamAndroidLogic
#

class StreamAndroidLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self):
        """
        Called when the logic class is instantiated. Can be used for initializing member variables.
        """
        ScriptedLoadableModuleLogic.__init__(self)
        self.outputNode = None

        # config = {'clientIndex'  : self.ui.deviceComboBox.currentValue(),
        #           'outputVolume' : self.ui.outputVolumeComboBox.currentNode(),
        #           'bitrate'      : self.ui.bitrateSpinBox.value(),
        #           'fpsSpinBox'   : self.ui.fpsSpinBox.value(),
        #           'maxWidth'     : self.ui.maxWidthSpinBox.value(),
        #           'flipImage'    : self.ui.flipImageCheckBox.checked,
        #           'stayAwake'      : self.ui.stayAwakeCheckBox.checked}

    def startStreaming(self, config):

        print(str(config))
        #Create the client
        device = adb.device_list()[config['clientIndex']]
        self.outputNode = config['outputVolume']

        #Setup client
        maxWidth, bitrate, max_fps, flip, stay_awake = config['maxWidth'], config['bitrate'], config['fpsSpinBox'], config['flipImage'], config['stayAwake']
        self.client = scrcpy.Client(device, maxWidth, bitrate, max_fps, flip, stay_awake)
        self.client.stop()
        time.sleep(1)
        self.client.start(threaded=True)
        time.sleep(1)

        #initialize the volume node with image data
        last_frame = self.client.last_frame
        frame_gray = cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)

        if self.outputNode is None:
            self.outputNode = slicer.util.addVolumeFromArray(frame_gray)
    
        while self.client.alive:
            slicer.app.processEvents()
            last_frame = self.client.last_frame
            frame_gray = cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)

            #Update the selected volume node with this data
            slicer.util.updateVolumeFromArray(self.outputNode, frame_gray)

    def stopStreaming(self, outputVolumeNode):
        #Remove the trackingObserver
        self.client.stop()


    def setDefaultParameters(self, parameterNode):
        """
        Initialize parameter node with default settings.
        """
        if not parameterNode.GetParameter("Threshold"):
            parameterNode.SetParameter("Threshold", "100.0")
        if not parameterNode.GetParameter("Invert"):
            parameterNode.SetParameter("Invert", "false")
