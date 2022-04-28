import numpy as np
import pyqtgraph as pg
from matplotlib import cm
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDesktopWidget, QDialog, QProgressBar, QPushButton

from facemap import utils
from facemap.pose import pose

from . import transforms

"""
Pose subclass for generating obtaining bounding box from user input.
Currently supports single video processing only.
"""


class PoseGUI(pose.Pose):
    def __init__(self, gui=None, img_xy=(256, 256)):
        self.gui = gui
        super(PoseGUI, self).__init__(gui=self.gui)
        self.bbox_set = False
        self.bbox = []
        self.resize = False
        self.add_padding = False
        self.img_xy = img_xy
        self.cancel_bbox_selection = False

    # Draw box on GUI using user's input
    def draw_user_bbox(self):
        """
        Function for user to draw a bbox
        """
        # Get sample frame from each video in case of multiple videos
        sample_frame = utils.get_frame(0, self.nframes, self.cumframes, self.containers)
        last_video = False
        for video_id, frame in enumerate(sample_frame):
            # Trigger new window for ROI selection of each frame
            if video_id == len(sample_frame) - 1:
                last_video = True
            ROI_popup(frame, video_id, self.gui, self, last_video)
        return self.bbox, self.bbox_set, self.resize, self.add_padding

    def plot_bbox_roi(self):
        # Plot bbox on GUI
        for i, bbox in enumerate(self.bbox):
            x1, x2, y1, y2 = bbox
            dy, dx = y2 - y1, x2 - x1
            xrange = np.arange(y1 + self.gui.sx[i], y2 + self.gui.sx[i]).astype(
                np.int32
            )
            yrange = np.arange(x1 + self.gui.sy[i], x2 + self.gui.sy[i]).astype(
                np.int32
            )
            x1, y1 = yrange[0], xrange[0]
            self.gui.add_ROI(
                roitype=4 + 1,
                roistr="bbox_{}".format(i),
                moveable=False,
                resizable=False,
                pos=(x1, y1, dx, dy),
                ivid=i,
                yrange=yrange,
                xrange=xrange,
            )
        self.bbox_set = True

    def adjust_bbox(self):
        # This function adjusts bbox so that it is of minimum dimension: 256, 256
        sample_frame = utils.get_frame(0, self.nframes, self.cumframes, self.containers)
        for i, bbox in enumerate(self.bbox):
            x1, x2, y1, y2 = bbox
            dy, dx = y2 - y1, x2 - x1
            if dx != dy:  # If bbox is not square then add padding to image
                self.add_padding = True
            larger_dim = max(dx, dy)
            if larger_dim < self.img_xy[0] or larger_dim < self.img_xy[1]:
                # If the largest dimension of the image is smaller than the minimum required dimension,
                # then resize the image to the minimum dimension
                self.resize = True
            else:
                # If the largest dimension of the image is larger than the minimum required dimension,
                # then crop the image to the minimum dimension
                (
                    x1,
                    x2,
                    y1,
                    y2,
                    self.resize,
                ) = transforms.get_crop_resize_params(
                    sample_frame[i],
                    x_dims=(x1,x2),
                    y_dims=(y1,y2),
                )
                self.bbox[i] = x1, x2, y1, y2
            print("BBOX after adjustment:", self.bbox)
            print("RESIZE:", self.resize)
            print("PADDING:", self.add_padding)


class ROI_popup(QDialog):
    def __init__(self, frame, video_id, gui, pose, last_video):
        super().__init__()
        window_max_size = QDesktopWidget().screenGeometry(-1)
        fraction = 0.3
        aspect_ratio = 1.2
        self.resize(
            int(np.floor(window_max_size.width() * fraction)),
            int(np.floor(window_max_size.height() * fraction * aspect_ratio)),
        )
        self.gui = gui
        self.frame = frame
        self.pose = pose
        self.last_video = last_video
        self.setWindowTitle("Select face ROI for video: " + str(video_id))

        # Add image and ROI bbox
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.win = pg.GraphicsLayoutWidget()
        self.win.setObjectName("Dialog " + str(video_id + 1))
        ROI_win = self.win.addViewBox(invertY=True)
        self.img = pg.ImageItem(self.frame)
        ROI_win.addItem(self.img)
        self.roi = pg.RectROI(
            [0, 0], [100, 100], pen=pg.mkPen("r", width=2), movable=True, resizable=True
        )
        ROI_win.addItem(self.roi)
        self.win.show()
        self.verticalLayout.addWidget(self.win)

        # Add buttons to dialog box
        self.done_button = QPushButton("Done")
        self.done_button.setDefault(True)
        self.done_button.clicked.connect(self.done_exec)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_exec)
        # Add a next button to the dialog box horizontally centered with cancel button and done button
        self.next_button = QPushButton("Next")
        self.next_button.setDefault(True)
        self.next_button.clicked.connect(self.next_exec)
        # Add a skip button to the dialog box horizontally centered with cancel button and done button
        self.skip_button = QPushButton("Skip")
        self.skip_button.setDefault(True)
        self.skip_button.clicked.connect(self.skip_exec)

        # Position buttons
        self.widget = QtWidgets.QWidget(self)
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.widget)
        self.horizontalLayout.setContentsMargins(-1, -1, -1, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.addWidget(self.cancel_button)
        self.horizontalLayout.addWidget(self.skip_button)
        if self.last_video:
            self.horizontalLayout.addWidget(self.done_button)
        else:
            self.horizontalLayout.addWidget(self.next_button)
        self.verticalLayout.addWidget(self.widget)

        self.exec_()

    def get_coordinates(self):
        roi_tuple, _ = self.roi.getArraySlice(self.frame, self.img, returnSlice=False)
        (x1, x2), (y1, y2) = roi_tuple[0], roi_tuple[1]
        return (x1, x2), (y1, y2)

    def skip_exec(self):
        self.pose.bbox = []
        self.pose.bbox_set = False
        self.close()

    def next_exec(self):
        (x1, x2), (y1, y2) = self.get_coordinates()
        self.pose.bbox.append([x1, x2, y1, y2])
        self.resize = False
        self.add_padding = False
        self.pose.adjust_bbox()
        self.close()

    def cancel_exec(self):
        self.pose.cancel_bbox_selection = True
        self.close()

    def done_exec(self):
        # User finished drawing ROI
        (x1, x2), (y1, y2) = self.get_coordinates()
        self.pose.bbox.append([x1, x2, y1, y2])
        self.resize = False
        self.add_padding = False
        self.pose.plot_bbox_roi()
        self.pose.adjust_bbox()
        self.close()


class VisualizeVideoSubset(QDialog):
    def __init__(self, gui, video_id, pose, frame_idx, bodyparts):
        super().__init__()
        print("Visualizing video subset")
        self.gui = gui
        self.video_id = video_id
        self.pose = pose
        self.frame_idx = frame_idx
        self.bodyparts = bodyparts

        print("pose shape:", self.pose.shape)
        colors = cm.get_cmap("jet")(np.linspace(0, 1.0, self.pose.shape[-2]))
        colors *= 255
        colors = colors.astype(int)
        self.brushes = np.array([pg.mkBrush(color=c) for c in colors])

        # Add image and pose prediction
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.win = pg.GraphicsLayoutWidget()
        self.win.setObjectName("Dialog " + str(video_id + 1))
        frame_win = self.win.addViewBox(invertY=True)
        self.current_frame_idx = 0
        frame0 = self.get_frame(self.frame_idx[self.current_frame_idx])
        self.img = pg.ImageItem(frame0)
        frame_win.addItem(self.img)
        self.win.show()
        self.verticalLayout.addWidget(self.win)
        self.update_window_title()

        self.button_horizontalLayout = QtWidgets.QHBoxLayout()
        # Add a next button to the dialog box horizontally centered with other buttons
        self.next_button = QPushButton("Next")
        self.next_button.setDefault(True)
        self.next_button.clicked.connect(self.next_exec)
        # Add a previous button to the dialog box horizontally centered with next button and done button
        self.previous_button = QPushButton("Previous")
        self.previous_button.setDefault(False)
        self.previous_button.clicked.connect(self.previous_exec)
        self.previous_button.setEnabled(False)
        # Add buttons to dialog box
        self.done_button = QPushButton("Done")
        self.done_button.setDefault(False)
        self.done_button.clicked.connect(self.done_exec)
        self.button_horizontalLayout.addWidget(self.previous_button)
        self.button_horizontalLayout.addWidget(self.next_button)
        self.button_horizontalLayout.addWidget(self.done_button)
        self.verticalLayout.addLayout(self.button_horizontalLayout)

        # Scatter plot for pose prediction
        self.pose_scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen("r", width=2))
        x, y = (
            self.pose[self.current_frame_idx][:, 0],
            self.pose[self.current_frame_idx][:, 1],
        )

        self.pose_scatter.setData(
            x=x,
            y=y,
            size=self.gui.sizeObject.height() * 0.006,
            symbol="o",
            brush=self.brushes,
            hoverable=True,
            hoverSize=self.gui.sizeObject.height() * 0.007,
            hoverSymbol="x",
            pen=(0, 0, 0, 0),
            data=self.bodyparts,
        )
        frame_win.addItem(self.pose_scatter)

        self.exec_()

    def get_frame(self, frame_idx):
        return utils.get_frame(
            frame_idx, self.gui.nframes, self.gui.cumframes, self.gui.video
        )[0]

    def next_exec(self):
        if self.current_frame_idx < len(self.frame_idx) - 1:
            self.current_frame_idx += 1
            self.update_window_title()
            self.img.setImage(self.get_frame(self.frame_idx[self.current_frame_idx]))
            self.update_pose_scatter()
            self.previous_button.setEnabled(True)
            if self.current_frame_idx == len(self.frame_idx) - 1:
                self.next_button.setEnabled(False)
        else:
            self.next_button.setEnabled(False)

    def previous_exec(self):
        if self.current_frame_idx > 0:
            self.current_frame_idx -= 1
            self.update_window_title()
            self.img.setImage(self.get_frame(self.frame_idx[self.current_frame_idx]))
            self.update_pose_scatter()
            self.next_button.setEnabled(True)
            if self.current_frame_idx == 0:
                self.previous_button.setEnabled(False)
        else:
            self.previous_button.setEnabled(False)

    def done_exec(self):
        self.close()

    def update_pose_scatter(self):
        x, y = (
            self.pose[self.current_frame_idx][:, 0],
            self.pose[self.current_frame_idx][:, 1],
        )
        self.pose_scatter.setData(
            x=x,
            y=y,
            size=self.gui.sizeObject.height() * 0.006,
            symbol="o",
            brush=self.brushes,
            hoverable=True,
            hoverSize=self.gui.sizeObject.height() * 0.005,
            hoverSymbol="x",
            pen=(0, 0, 0, 0),
            data=self.bodyparts,
        )

    def update_window_title(self):
        self.setWindowTitle(
            "Frame: "
            + str(self.frame_idx[self.current_frame_idx])
            + " ({}/{})".format(self.current_frame_idx, len(self.frame_idx) - 1)
        )


class ProgressBarPopup(QDialog):
    def __init__(self, gui):
        super().__init__(gui)
        self.gui = gui
        self.setWindowTitle("Training model...")
        window_size = QDesktopWidget().screenGeometry(-1)
        self.setFixedSize(
            int(np.floor(window_size.width() * 0.31)),
            int(np.floor(window_size.height() * 0.31 * 0.5)),
        )
        self.verticalLayout = QtWidgets.QVBoxLayout(self)

        self.progress_bar = QProgressBar(gui)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedSize(
            int(np.floor(window_size.width() * 0.3)),
            int(np.floor(window_size.height() * 0.3 * 0.2)),
        )
        self.progress_bar.show()
        # Add the progress bar to the dialog
        self.verticalLayout.addWidget(self.progress_bar)

        # Add a cancel button to the dialog
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.close)
        self.verticalLayout.addWidget(cancel_button)

        self.show()

    def update_progress_bar(self, message, gui_obj):
        message = message.getvalue().split("\x1b[A\n\r")[0].split("\r")[-1]
        progressBar_value = [
            int(s) for s in message.split("%")[0].split() if s.isdigit()
        ]
        if len(progressBar_value) > 0:
            progress_percentage = int(progressBar_value[0])
            self.progress_bar.setValue(progress_percentage)
            self.progress_bar.setFormat(str(progress_percentage) + " %")
        gui_obj.QApplication.processEvents()
