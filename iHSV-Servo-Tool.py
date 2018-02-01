# iHSV Servo Tool
# Copyright (C) 2018 Robert Budde

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtSerialPort import QSerialPortInfo

import pyqtgraph as pg

import time
import numpy as np
import serial
import minimalmodbus


class ModBusDataPlot(QWidget):

    signalAttachToAxis = pyqtSignal(pg.PlotCurveItem, bool, name='AttachToAxis')

    def __init__(self, name='None', registers=[], signed=False, settings=None):
        super().__init__(None)

        self.name = name
        self.registers = registers
        self.signed = signed
        self.settings = settings

        self.colorButton = QPushButton()
        self.colorButton.setFixedWidth(20)
        self.colorButton.setFixedHeight(20)
        self.colorButton.clicked.connect(self.chooseColor)
        self.color = QColor(255,255,255)

        self.label = QLabel(name)
        self.activeCheckbox = QCheckBox('Active')
        self.activeCheckbox.toggled.connect(self.setActive)
        self.axisCheckbox = QCheckBox('2nd Y')
        self.axisCheckbox.toggled.connect(self.attachToAxis)
        self.layout = QGridLayout(self)
        self.layout.addWidget(self.colorButton, 0, 0, 1, 2)
        self.layout.setColumnMinimumWidth(0, 30)
        self.layout.addWidget(self.label, 0, 1, 1, 2)
        self.layout.setColumnMinimumWidth(1, 100)
        self.layout.setColumnStretch(1, 0.5)
        self.layout.addWidget(self.activeCheckbox, 0, 2)
        self.layout.addWidget(self.axisCheckbox, 1, 2)
        self.layout.setColumnMinimumWidth(2, 50)
        self.layout.setColumnStretch(2, 0.5)

        self.curve = pg.PlotCurveItem(connect="finite")
        self.curve.setPos(-1000, 0)
        self.data = np.empty(1001)
        self.data.fill(np.nan)

        self.readSettings()

    def readSettings(self):
        try:
            self.setColor(self.settings.value(self.name + "/Color", QColor(255,255,255)))
            self.activeCheckbox.setChecked(self.settings.value(self.name + "/Active", False, type=bool))
            self.axisCheckbox.setChecked(self.settings.value(self.name + "/2ndAxis", False, type=bool))
        except:
            pass

    def writeSettings(self):
        try:
            self.settings.setValue(self.name + "/Color", self.color)
            self.settings.setValue(self.name + "/Active", self.activeCheckbox.isChecked())
            self.settings.setValue(self.name + "/2ndAxis", self.axisCheckbox.isChecked())
        except:
            pass

    def setColor(self, color):
        if color.isValid():
            self.color = color
            self.colorButton.setStyleSheet("QPushButton { background-color: %s }" % (color.name()))
            pen = pg.mkPen(self.color, width=2)
            self.curve.setPen(pen)

    def chooseColor(self):
        color = QColorDialog.getColor(self.color)
        self.setColor(color)

    def setActive(self):
        if self.isActive():
            self.curve.setData(self.data)
        else:
            self.curve.setData([])

    def attachToAxis(self):
        self.signalAttachToAxis.emit(self.curve, self.axisCheckbox.isChecked())

    def update(self, rawValues):
        self.data = np.roll(self.data,-1)
        if len(rawValues) == 2:
            value = (rawValues[0] << 16) | rawValues[1]
            if (0x80000000 & value): 
                value = - (0x0100000000 - value)
        elif self.signed:
            value = rawValues[0]
            if (0x8000 & value): 
                value = - (0x010000 - value)
        else:
            value = rawValues[0]

        self.data[-1] = value
        self.curve.setData(self.data)

    def fadeOut(self):
        self.data = np.roll(self.data,-1)
        self.data[-1] = np.nan

    def resetData(self):
        self.data.fill(np.nan)       
        self.curve.setData([])

    def getRegisters(self):
        return self.registers

    def isActive(self):
        return self.activeCheckbox.isChecked()

class MainWindow(QMainWindow):
    configDataInfos = [
        [0x06, 'Control Mode'],
        [0x07, 'Control Mode Signal'],
        [0x08, 'Mode 2'],
        [0x0A, 'Motor/Encoder: Line'],
        [0x31, 'Input offset'],
        [0x32, 'Simulation command weighted coefficient'],
        [0x46, 'Electronic gear: Nominator'],
        [0x47, 'Electronic gear: Denominator'],
        [0x40, 'Pp'],
        [0x41, 'Pd'],
        [0x42, 'Pff'],
        [0x45, 'Pos Filter'],
        [0x48, 'Pos Error'],

        [0x50, 'Vp'],
        [0x51, 'Vi'],
        [0x52, 'Vd'],
        [0x53, 'Aff'],
        [0x54, 'Vel Filter'],
        [0x55, 'Continuous Vel'],
        [0x56, 'Vel Limit'],
        [0x57, 'Acc'],
        [0x58, 'Dec'],

        [0x60, 'Cp'],
        [0x61, 'Ci'],
        [0x62, 'Continuous Current'],
        [0x63, 'Limit Current'],

        [0x3A, 'Temp Limit'],
        [0x3B, 'Over Voltage Limit'],
        [0x3C, 'Under Voltage Limit'],
        [0x3D, 'I2T Limit'],
    ]

    liveDataInfos = [
        [[0x85,0x86], False, 'Pos Cmd'],
        [[0x87,0x88], False, 'Real Pos'],
        [[0x89], True, 'Pos Error'],
        [[0x90], True, 'Vel Cmd [Rpm]'],
        [[0x91], True, 'Real Vel [Rpm]'],
        [[0x92], True, 'Vel Error [Rpm]'],
        [[0xA0], True, 'Torque Current Cmd'],
        [[0xA1], True, 'Real Torque Current'],
    ]

    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("iHSV57 Servo Tool")
        
        self.settings = QSettings("IBB", "iHSV57 Servo Tool")

        ## Define a top-level widget to hold everything
        self.widget = QWidget()

        ## Create a grid layout to manage the widgets size and position
        self.layout = QGridLayout()
        self.widget.setLayout(self.layout)

        ## Create some widgets to be placed inside
        self.cbSelectComport = QComboBox()
        self.pbOpenCloseComport = QPushButton('Open Comport')
        self.pbOpenCloseComport.clicked.connect(self.openCloseComport)
        self.pbReadParams = QPushButton('Read Parameters')
        self.pbReadParams.clicked.connect(self.readParams)     
        self.pbStartStopMonitor = QPushButton('Start Monitor')
        self.pbStartStopMonitor.setFixedHeight(100)
        self.pbStartStopMonitor.clicked.connect(self.startStopMonitor)     

        self.ParamTable = QTableWidget(20, 3, self)
        self.ParamTable.setHorizontalHeaderLabels(('Register', 'Value', 'Description'))
        self.ParamTable.horizontalHeaderItem(0).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ParamTable.horizontalHeaderItem(1).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ParamTable.horizontalHeaderItem(2).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.ParamTable.horizontalHeader().setResizeMode(0, QHeaderView.ResizeToContents)
        self.ParamTable.horizontalHeader().setResizeMode(1, QHeaderView.ResizeToContents)
        self.ParamTable.horizontalHeader().setResizeMode(2, QHeaderView.Stretch)

        pg.setConfigOptions(antialias=False)
        self.plot = pg.PlotWidget()
        self.plot.setDownsampling(mode='peak')
        self.plot.setClipToView(True)
        self.plot.setXRange(-100, 0)
        self.plot.setYRange(-200, 200)
        self.plot.setLimits(xMin=-1000,xMax=0,minXRange=20,maxXRange=1000)
        self.plot.setLabel('bottom', text='Time', units='s')
        self.plot.getAxis('bottom').setScale(0.01)
        self.plot.showAxis('right')

        self.plot2ndAxis = pg.ViewBox()
        self.plot.scene().addItem(self.plot2ndAxis)
        self.plot.getAxis('right').linkToView(self.plot2ndAxis)
        self.plot2ndAxis.setXLink(self.plot)
        self.plot2ndAxis.setYRange(-10,10)

        def updateViews():
            self.plot2ndAxis.setGeometry(self.plot.getViewBox().sceneBoundingRect())
            self.plot2ndAxis.linkedViewChanged(self.plot.getViewBox(), self.plot2ndAxis.XAxis)

        updateViews()
        self.plot.getViewBox().sigResized.connect(updateViews)

        vbox = QVBoxLayout()
        self.mdps = [];
        for liveDataInfo in self.liveDataInfos:
            mdp = ModBusDataPlot(liveDataInfo[2], liveDataInfo[0], liveDataInfo[1], settings=self.settings)
            mdp.signalAttachToAxis.connect(self.attachToAxis)
            mdp.attachToAxis()
            self.mdps.append(mdp)
            vbox.addWidget(mdp);

        self.groupBox = QGroupBox('Data plots')
        vbox.addStretch(1);
        self.groupBox.setLayout(vbox);

        ## Add widgets to the layout in their proper positions
        self.layout.addWidget(self.plot, 0, 0, 1, 2)  # plot goes on top, spanning 2 columns
        self.layout.addWidget(self.groupBox, 0, 2)  # legend to the right
        self.layout.setColumnMinimumWidth(0, 200)
        self.layout.setColumnStretch(1, 1)
        self.layout.setColumnMinimumWidth(1, 200)
        self.layout.setColumnMinimumWidth(2, 200)
        self.layout.addWidget(self.cbSelectComport, 1, 0)   # comport-combobox goes in upper-left
        self.layout.addWidget(self.pbOpenCloseComport, 2, 0)   # open/close button goes in middle-left
        self.layout.addWidget(self.pbReadParams, 3, 0)
        self.layout.addWidget(self.pbStartStopMonitor, 4, 0)
        self.layout.addWidget(self.ParamTable, 1, 1, 4, 2)  # list widget goes in bottom-left

        self.setCentralWidget(self.widget)

        self.createActions()

        comports = QSerialPortInfo.availablePorts()
        for comport in comports:
            self.cbSelectComport.addItem(comport.portName());

        self.readSettings()
        
        self.statusBar().showMessage("Ready", 2000)

    def attachToAxis(self, curve, secondAxis):
        if secondAxis:
            if curve in self.plot.listDataItems():
                self.plot.removeItem(curve)
            self.plot2ndAxis.addItem(curve)
        else:
            if curve in self.plot.listDataItems():
                self.plot2ndAxis.removeItem(curve)
            self.plot.addItem(curve)

    def openCloseComport(self):
        if (self.pbOpenCloseComport.text() == 'Open Comport'):
            try:
                self.servo = minimalmodbus.Instrument(self.cbSelectComport.currentText(), 1)
                self.servo.serial.baudrate = 57600   # Baud
                self.servo.serial.bytesize = 8
                self.servo.serial.parity   = serial.PARITY_NONE
                self.servo.serial.stopbits = 1
                self.servo.serial.timeout  = 0.5   # seconds
            except:
                self.statusBar().showMessage("Failed to open port", 2000)
                return
            self.pbOpenCloseComport.setText('Close Comport')
            try:
                self.servo.read_register(0x80)
            except:
                self.statusBar().showMessage("Device does not respond", 2000)
                return            
            self.statusBar().showMessage("Port opened successfully", 2000)
        else:
            try:
                self.servo.serial.close()
                self.statusBar().showMessage("Port closed", 2000)
            except:
                pass
            self.pbOpenCloseComport.setText('Open Comport')

    def readParams(self):
        if (self.pbOpenCloseComport.text() == 'Open Comport'):
            return
        try:
            self.ParamTable.cellChanged.disconnect(self.writeParams)
        except Exception:
            pass
        self.statusBar().showMessage("Loading System Params...", 2000)
        self.ParamTable.setRowCount(len(self.configDataInfos))
        row = 0
        for configDataInfo in self.configDataInfos:
            res = self.servo.read_register(configDataInfo[0])
            item = QTableWidgetItem('0x{0:02X}'.format(configDataInfo[0]))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.ParamTable.setItem(row, 0, item)
            item = QTableWidgetItem('{0:5d}'.format(res))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.ParamTable.setItem(row, 1, item)
            self.ParamTable.setItem(row, 2, QTableWidgetItem(configDataInfo[1]))
            row = row + 1
        self.ParamTable.cellChanged.connect(self.writeParams)
        self.statusBar().showMessage("Loading System Params done!", 2000)

    def writeParams(self, row, column):
        if (self.pbOpenCloseComport.text() == 'Open Comport'):
            return
        if column != 1:
            return
        try:
            value = int(self.ParamTable.item(row, column).text())
        except:
            self.statusBar().showMessage("Failed to convert Config Value...", 2000)
            return
        reg = self.configDataInfos[row][0]
        self.servo.write_register(reg, value, functioncode=6)
        self.statusBar().showMessage("Writing {0} to 0x{1:02x} done!".format(value, reg), 2000)

    def updatePlots(self):
        for mdp in self.mdps:
            if mdp.isActive():
                regs = mdp.getRegisters()
                values = self.servo.read_registers(regs[0], len(regs))
                mdp.update(values)
            else:
                mdp.fadeOut()

    def startStopMonitor(self):
        if (self.pbOpenCloseComport.text() == 'Open Comport'):
            return
        if (self.pbStartStopMonitor.text() == 'Start Monitor'):
            self.monitorTimer = QTimer()
            self.monitorTimer.timeout.connect(self.updatePlots)
            self.monitorTimer.start(10)
            self.pbStartStopMonitor.setText('Stop Monitor')      
            self.statusBar().showMessage("Monitor started", 2000)
            for mdp in self.mdps:
                mdp.resetData()
        else:
            self.monitorTimer.stop()
            self.statusBar().showMessage("Monitor stopped", 2000)
            self.pbStartStopMonitor.setText('Start Monitor')

    def closeEvent(self, event):
        self.writeSettings()
        event.accept()

    def createActions(self):
        self.exitAct = QAction("E&xit", self, shortcut="Ctrl+Q",
                statusTip="Exit the application", triggered=self.close)

    def readSettings(self):
        self.settings = QSettings("IBB", "iHSV57 Servo Tool")
        self.move(self.settings.value("pos", QPoint(100, 100)))
        self.resize(self.settings.value("size", QSize(800, 600)))
        self.cbSelectComport.setCurrentText(self.settings.value("comport", self.cbSelectComport.currentText()))

    def writeSettings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("size", self.size())
        self.settings.setValue("comport", self.cbSelectComport.currentText())
        for mdp in self.mdps:
            mdp.writeSettings()

if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())
