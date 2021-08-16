import sys
import inspect
import json

import maya.api.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx
import maya.cmds as cmds
from pymel.core.windows import Callback, CallbackWithArgs

StreamTypesPerSubjectType = {
    "Prop": 		["Root Only", "Full Hierarchy"],
    "Character":	["Root Only", "Full Hierarchy"],
    "Camera":		["Root Only", "Full Hierarchy", "Camera"],
    "Light":		["Root Only", "Full Hierarchy", "Light"],
}


def OnRemoveSubject(SubjectPath):
    cmds.LiveLinkRemoveSubject(SubjectPath)
    RefreshSubjects()


def CreateSubjectTable():
    if not cmds.window(MayaLiveLinkUI.WindowName, exists=True):
        return

    cmds.rowColumnLayout(
        "SubjectLayout", numberOfColumns=5,
        columnWidth=[(1, 20), (2, 80), (3, 100), (4, 180), (5, 120)],
        columnOffset=[(1, 'right', 5), (2, 'right', 10), (4, 'left', 10)],
        parent="SubjectWrapperLayout")
    cmds.text(label="")
    cmds.text(label="Subject Type", font="boldLabelFont", align="left")
    cmds.text(label="Subject Name", font="boldLabelFont", align="left")
    cmds.text(label="DAG Path", font="boldLabelFont", align="left")
    cmds.text(label="Stream Type", font="boldLabelFont", align="left")
    cmds.rowColumnLayout(
        "SubjectLayout", edit=True, rowOffset=(1, "bottom", 10))


# Populate subjects list from c++
def PopulateSubjects():
    SubjectNames = cmds.LiveLinkSubjectNames()
    SubjectPaths = cmds.LiveLinkSubjectPaths()
    SubjectTypes = cmds.LiveLinkSubjectTypes()
    SubjectRoles = cmds.LiveLinkSubjectRoles()
    if SubjectPaths is not None:
        RowCounter = 0
        for (SubjectName, SubjectPath, SubjectType, SubjectRole) in zip(
                SubjectNames, SubjectPaths, SubjectTypes, SubjectRoles):
            cmds.button(
                label="-", height=21,
                command=Callback(OnRemoveSubject, SubjectPath),
                parent="SubjectLayout")
            cmds.text(
                label=SubjectType, height=21, align="left",
                parent="SubjectLayout")
            cmds.textField(
                text=SubjectName, height=21,
                changeCommand=CallbackWithArgs(
                    cmds.LiveLinkChangeSubjectName,
                    SubjectPath),
                parent="SubjectLayout")
            cmds.text(
                label=SubjectPath, align="left", height=21,
                parent="SubjectLayout")

            # adding a trailing index makes the name unique which is required
            # by the api
            LayoutName = "ColumnLayoutRow_" + str(RowCounter)

            cmds.columnLayout(LayoutName, parent="SubjectLayout")
            cmds.optionMenu(
                "SubjectTypeMenu", parent=LayoutName, height=21,
                changeCommand=CallbackWithArgs(
                    cmds.LiveLinkChangeSubjectStreamType, SubjectPath))

            for StreamType in StreamTypesPerSubjectType[SubjectType]:
                cmds.menuItem(label=StreamType)

            # menu items are 1-indexed
            StreamTypeIndex = \
                StreamTypesPerSubjectType[SubjectType].index(SubjectRole) + 1
            cmds.optionMenu(
                "SubjectTypeMenu", edit=True, select=StreamTypeIndex)

            RowCounter += 1


def ClearSubjects():
    if (cmds.window(MayaLiveLinkUI.WindowName, exists=True)):
        cmds.deleteUI("SubjectLayout")


# Refresh subjects list
def RefreshSubjects():
    if (cmds.window(MayaLiveLinkUI.WindowName, exists=True)):
        cmds.deleteUI("SubjectLayout")
        CreateSubjectTable()
        PopulateSubjects()


# Connection UI Colours
ConnectionActiveColour = [0.71, 0.9, 0.1]
ConnectionInactiveColour = [1.0, 0.4, 0.4]
ConnectionColourMap = {
    True: ConnectionActiveColour,
    False: ConnectionInactiveColour
}


# Base class for command (common creator method + allows for automatic
# register/unregister)
class LiveLinkCommand(OpenMayaMPx.MPxCommand):
    def __init__(self):
        OpenMayaMPx.MPxCommand.__init__(self)

    @classmethod
    def Creator(Cls):
        return OpenMayaMPx.asMPxPtr(Cls())


# Is supplied object a live link command
def IsLiveLinkCommand(InCls):
    return (
        inspect.isclass(InCls) and
        issubclass(InCls, LiveLinkCommand) and
        InCls != LiveLinkCommand)


# Given a list of strings of names return all the live link commands listed
def GetLiveLinkCommandsFromModule(ModuleItems):
    EvalItems = (eval(Item) for Item in ModuleItems)
    return [Command for Command in EvalItems if IsLiveLinkCommand(Command)]


# Command to create the Live Link UI
class MayaLiveLinkUI(LiveLinkCommand):
    WindowName = "MayaLiveLinkUI"
    Title = "Maya Live Link UI"
    WindowSize = (500, 300)

    def __init__(self):
        LiveLinkCommand.__init__(self)

    # Invoked when the command is run.
    def doIt(self, argList):
        if (cmds.window(self.WindowName, exists=True)):
            cmds.deleteUI(self.WindowName)
        cmds.window(
            self.WindowName, title=self.Title, menuBar=True,
            widthHeight=(self.WindowSize[0], self.WindowSize[1]))

        # Get current connection status
        ConnectionText, ConnectedState = cmds.LiveLinkConnectionStatus()

        cmds.columnLayout("mainColumn", adjustableColumn=True)
        cmds.rowLayout(
            "HeaderRow", numberOfColumns=3, adjustableColumn=1,
            parent="mainColumn")
        cmds.text(label="Unreal Engine Live Link", align="left")
        cmds.text(label="Connection:")
        cmds.text(
            "ConnectionStatusUI", label=ConnectionText, align="center",
            backgroundColor=ConnectionColourMap[ConnectedState], width=150)

        cmds.separator(h=20, style="none", parent="mainColumn")

        # just used as a container that will survive refreshing, so the
        # following controls stay in their correct place
        cmds.columnLayout("SubjectWrapperLayout", parent="mainColumn")

        CreateSubjectTable()
        PopulateSubjects()

        cmds.separator(h=20, style="none", parent="mainColumn")
        cmds.button(
            label='Add Selection', parent="mainColumn",
            command=self.AddSelection)

        SettingsMenu = cmds.menu(label='Settings', parent=self.WindowName)
        cmds.menuItem(
            label='Network Endpoints', parent=SettingsMenu,
            command=self.ShowNetworkEndpointsDialog)

        cmds.showWindow(self.WindowName)

    def AddSelection(self, *args):
        cmds.LiveLinkAddSelection()
        RefreshSubjects()

    def ShowNetworkEndpointsDialog(self, *args, **kwargs):
        # Store the current endpoint settings.
        UnicastEndpoint = cmds.LiveLinkMessagingSettings(
            q=True, unicastEndpoint=True)
        StaticEndpoints = cmds.LiveLinkMessagingSettings(
            q=True, staticEndpoints=True)

        def CreateUI():
            Form = cmds.setParent(q=True)

            DialogLayout = cmds.columnLayout(
                "NetworkEndpointsDialogLayout", parent=Form,
                columnWidth=400)

            EndpointsLayout = cmds.rowColumnLayout(
                "EndpointsLayout", parent=DialogLayout,
                numberOfColumns=2, adjustableColumn=2,
                columnWidth=[(1, 100), (2, 300)],
                columnOffset=[(1, 'left', 5), (2, 'left', 5)])

            cmds.text(
                parent=EndpointsLayout, label="Unicast Endpoint:",
                font="boldLabelFont", height=30, align="left")
            UnicastTextField = cmds.textField(
                parent=EndpointsLayout, text=UnicastEndpoint,
                placeholderText='X.X.X.X:X')

            cmds.text(
                parent=EndpointsLayout, label="Static Endpoints:",
                font="boldLabelFont", height=30, align="left")
            StaticTextField = cmds.textField(
                parent=EndpointsLayout, text=','.join(StaticEndpoints),
                placeholderText='X.X.X.X:X,Y.Y.Y.Y:Y,...')

            def _OnCancel(*args, **kwargs):
                cmds.layoutDialog(dismiss="")

            def _OnOk(*args, **kwargs):
                NewUnicastEndpoint = cmds.textField(
                    UnicastTextField, q=True, text=True).strip()
                if not NewUnicastEndpoint:
                    # Revert to the default unicast endpoint if the
                    # text field is emptied.
                    NewUnicastEndpoint = '0.0.0.0:0'

                NewStaticEndpoints = cmds.textField(
                    StaticTextField, q=True, text=True).strip() or []
                if NewStaticEndpoints:
                    NewStaticEndpoints = [
                        Endpoint.strip() for Endpoint in
                        NewStaticEndpoints.split(',')]

                EndpointsDict = {
                    'unicast': NewUnicastEndpoint,
                    'static': NewStaticEndpoints
                }

                cmds.layoutDialog(dismiss=json.dumps(EndpointsDict))

            ButtonsLayout = cmds.rowLayout(
                "ButtonsLayout", parent=DialogLayout, numberOfColumns=2,
                columnWidth=[(1, 200), (2, 200)])
            cmds.button(
                parent=ButtonsLayout, label='Cancel', width=200, height=30,
                command=_OnCancel)
            cmds.button(
                parent=ButtonsLayout, label='Ok', width=200, height=30,
                command=_OnOk)

        result = cmds.layoutDialog(ui=CreateUI, title='Set Network Endpoints')
        if result:
            # Apply new endpoint settings if they differ from the current
            # settings.
            EndpointsDict = json.loads(result)
            NewUnicastEndpoint = EndpointsDict['unicast']
            NewStaticEndpoints = EndpointsDict['static']

            if NewUnicastEndpoint != UnicastEndpoint:
                cmds.LiveLinkMessagingSettings(
                    NewUnicastEndpoint, unicastEndpoint=True)

            if NewStaticEndpoints != StaticEndpoints:
                RemovedStaticEndpoints = list(
                    set(StaticEndpoints) - set(NewStaticEndpoints))
                AddedStaticEndpoints = list(
                    set(NewStaticEndpoints) - set(StaticEndpoints))

                if RemovedStaticEndpoints:
                    cmds.LiveLinkMessagingSettings(
                        *RemovedStaticEndpoints, staticEndpoints=True,
                        removeEndpoint=True)
                if AddedStaticEndpoints:
                    cmds.LiveLinkMessagingSettings(
                        *AddedStaticEndpoints, staticEndpoints=True,
                        addEndpoint=True)


# Command to Refresh the subject UI
class MayaLiveLinkRefreshUI(LiveLinkCommand):
    def __init__(self):
        LiveLinkCommand.__init__(self)

    # Invoked when the command is run.
    def doIt(self, argList):
        RefreshSubjects()


# Command to Refresh the connection UI
class MayaLiveLinkRefreshConnectionUI(LiveLinkCommand):
    def __init__(self):
        LiveLinkCommand.__init__(self)

    # Invoked when the command is run.
    def doIt(self, argList):
        if (cmds.window(MayaLiveLinkUI.WindowName, exists=True)):
            # Get current connection status
            ConnectionText, ConnectedState = cmds.LiveLinkConnectionStatus()
            cmds.text(
                "ConnectionStatusUI", edit=True, label=ConnectionText,
                backgroundColor=ConnectionColourMap[ConnectedState])


# Grab commands declared
Commands = GetLiveLinkCommandsFromModule(dir())

AfterPluginUnloadCallbackId = None


def AfterPluginUnloadCallback(stringArray, clientData):
    for stringVal in stringArray:
        if stringVal.startswith('MayaLiveLinkPlugin'):
            ClearSubjects()
            CreateSubjectTable()
            return


# Initialize the script plug-in
def initializePlugin(mobject):
    mplugin = OpenMayaMPx.MFnPlugin(mobject)

    print("LiveLink:")
    for Command in Commands:
        try:
            print("\tRegistering Command '%s'" % Command.__name__)
            mplugin.registerCommand(Command.__name__, Command.Creator)
        except Exception:
            sys.stderr.write(
                "Failed to register command: %s\n" % Command.__name__)
            raise

    global AfterPluginUnloadCallbackId
    AfterPluginUnloadCallbackId = \
        OpenMaya.MSceneMessage.addStringArrayCallback(
            OpenMaya.MSceneMessage.kAfterPluginUnload,
            AfterPluginUnloadCallback)


# Uninitialize the script plug-in
def uninitializePlugin(mobject):
    mplugin = OpenMayaMPx.MFnPlugin(mobject)

    global AfterPluginUnloadCallbackId
    if AfterPluginUnloadCallbackId is not None:
        OpenMaya.MSceneMessage.removeCallback(AfterPluginUnloadCallbackId)
        AfterPluginUnloadCallbackId = None

    for Command in Commands:
        try:
            mplugin.deregisterCommand(Command.__name__)
        except Exception:
            sys.stderr.write(
                "Failed to unregister command: %s\n" % Command.__name__)
