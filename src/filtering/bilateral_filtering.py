import cv2
import numpy as np
import pytesseract
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QPushButton,
    QLabel,
    QSlider,
    QVBoxLayout,
    QComboBox,
    QMessageBox,
    QHBoxLayout,
    QCheckBox
)

from src.util.dialog import open_image_dialog
from src.util.accuracy import calculate_accuracy
from src.util.save import save_image
from src.util.histogram import HistogramWindow
from src.util.dilate_image import dilate_image

max_width = 450
max_height = 450


class BilateralFiltering(QWidget):
    """
    A GUI widget for applying bilateral filtering to an image.

    This class provides a GUI for selecting an image and applying bilateral filtering to it.
    Users can adjust the diameter and sigmaColor parameters to customize the filtering. Additionally,
    the user can view the original grayscale image and a bilateral filtered image, as well as obtain computer-extracted
    text from either of these images. The user may also save the preprocessed binary image with
    a specific filename, image format, and directory. The user can also display and save the corresponding histogram
    graphs of these images as well.

    If the user provides a clean version of the image, the user can see the differences between the extracted
    text of the clean image and any of the other images. On top of that, the feature will also provide a text
    extraction accuracy value.

    The user can also check a box to bold the text through a dilation of size 2x2.

    Attributes:
        image (np.ndarray): The currently displayed image.
        clean_image (np.ndarray): The clean version of the image for accuracy calculation.
        titles (list): A list of titles for different image display options.
    """

    image: np.ndarray
    clean_image: np.ndarray
    titles = ["Original Image", "Bilateral Filtering"]

    def __init__(self):
        """
        Initializes the bilateral filtering window of the application.
        """

        # Initialize the parent class (QWidget)
        super().__init__()

        self.setWindowTitle("Bilateral Filtering")

        # Go through the titles and allow the user to see them and choose one through a combo box.
        self.method_combobox = QComboBox()
        for title in self.titles:
            self.method_combobox.addItem(title)
        self.method_combobox.currentIndexChanged.connect(self.update_image)

        # Allow the user to check a box to "bold the text" by performing dilation
        self.dilation_request = QCheckBox("Bold Text")
        self.dilation_request.stateChanged.connect(self.update_image)

        # Have labels to keep track of the given noisy and clean files
        self.noisy_label = QLabel("Noisy File: N/A")
        self.clean_label = QLabel("Clean File: N/A")

        # Set initial parameters
        self.diameter = 5
        self.sigma_color = 75

        # Label that will keep track of the user-inputted diameter
        self.diameter_label = QLabel(f"Diameter: {self.diameter}")

        # Create a QSlider that the user can interact with to dynamically change the diameter value
        self.diameter_slider = QSlider()
        self.diameter_slider.setOrientation(Qt.Horizontal)
        self.diameter_slider.setTickPosition(QSlider.TicksBelow)
        self.diameter_slider.setMinimum(1)
        self.diameter_slider.setMaximum(21)
        self.diameter_slider.setTickInterval(2)
        self.diameter_slider.setValue(self.diameter)

        # When the diameter slider's value is changed, update the instance's diameter and the image label
        self.diameter_slider.valueChanged.connect(self.on_diameter_change)

        # Label that will keep track of the user-inputted sigmaColor
        self.sigma_color_label = QLabel(f"Sigma Color: {self.sigma_color}")

        # Create a QSlider that the user can interact with to dynamically change the sigmaColor value
        self.sigma_color_slider = QSlider()
        self.sigma_color_slider.setOrientation(Qt.Horizontal)
        self.sigma_color_slider.setTickPosition(QSlider.TicksBelow)
        self.sigma_color_slider.setMinimum(1)
        self.sigma_color_slider.setMaximum(255)
        self.sigma_color_slider.setValue(self.sigma_color)

        # When the sigmaColor slider's value is changed, update instance's sigmaColor and the image label
        self.sigma_color_slider.valueChanged.connect(self.on_sigma_color_change)

        # Label that will hold the desired image
        self.image_label = QLabel()
        self.clean_image_label = QLabel()

        # Initialize the image label
        self.image = np.tile(np.arange(225, dtype=np.uint8).repeat(2), (450, 1))
        q_img = QImage(self.image.data, 450, 450, 450, QImage.Format_Indexed8)
        self.image_label.setPixmap(QPixmap.fromImage(q_img))

        # Wait to display the histogram window until the user requests it
        self.histogram_window = None

        # Prepare to use a compressed image if the provided image is too large to fit in the GUI
        self.compressed_img = None

        # Prepare a button that when pushed will open the file dialog for the user
        open_image_btn = QPushButton("Open Image", self)
        open_image_btn.clicked.connect(self.open_image)

        # Prepare an extract text button that will utilize the current image and slider values
        extract_text_btn = QPushButton("Extract Text", self)
        extract_text_btn.clicked.connect(self.extract_text)

        # Prepare a button to provide a clean version of the image
        provide_clean_image_btn = QPushButton("Provide Clean Image", self)
        provide_clean_image_btn.clicked.connect(self.provide_clean_image)

        # Prepare a button to allow the user to save the preprocessed binary image
        save_btn = QPushButton("Save Preprocessed Binary Image", self)
        save_btn.clicked.connect(self.prepare_to_save)

        # Prepare a button to show the histogram
        show_histogram_btn = QPushButton("Show/Hide Histogram")
        show_histogram_btn.clicked.connect(self.show_histogram)

        provide_help_btn = QPushButton("Help", self)
        provide_help_btn.clicked.connect(self.provide_help)

        button_layout = QHBoxLayout()
        button_layout.addWidget(extract_text_btn)
        button_layout.addWidget(provide_clean_image_btn)
        button_layout.addWidget(show_histogram_btn)
        button_layout.addWidget(provide_help_btn)

        preprocessing_layout = QHBoxLayout()
        preprocessing_layout.addWidget(self.method_combobox)
        preprocessing_layout.addWidget(self.dilation_request)

        image_layout = QHBoxLayout()
        image_layout.addWidget(self.image_label)
        image_layout.addWidget(self.clean_image_label)

        # Create layout and add widgets
        layout = QVBoxLayout()
        layout.addWidget(open_image_btn)
        layout.addLayout(preprocessing_layout)
        layout.addWidget(self.noisy_label)
        layout.addWidget(self.clean_label)
        layout.addWidget(self.diameter_label)
        layout.addWidget(self.diameter_slider)
        layout.addWidget(self.sigma_color_label)
        layout.addWidget(self.sigma_color_slider)
        layout.addLayout(image_layout)
        layout.addLayout(button_layout)
        layout.addWidget(save_btn)

        # Set dialog layout
        self.setLayout(layout)

    def open_image(self):
        """
        Opens a file dialog and displays the user-selected image.
        """

        # Allow the user to select an image
        image, file_name = open_image_dialog()

        # Check if the user gave an image with a valid format. If so, update the instance's image
        # attribute and update the image label.
        if image is not None:
            self.image = np.array(image)
            self.noisy_label.setText("Noisy File: " + file_name)
            if image.shape[0] > max_height and image.shape[1] > max_width:     # Both height and width are too large
                image = cv2.resize(image, (max_width, max_height))
                self.compressed_img = np.array(image)
            elif image.shape[0] > max_height and image.shape[1] <= max_width:  # Height is too large
                image = cv2.resize(image, (image.shape[1], max_height))
                self.compressed_img = np.array(image)
            elif image.shape[0] <= max_height and image.shape[1] > max_width:  # Width is too large
                image = cv2.resize(image, (max_width, image.shape[0]))
                self.compressed_img = np.array(image)
            self.update_image()
        else:
            QMessageBox.warning(self, "Error", "Did not receive a valid image!")

    def update_image(self):
        """
        Updates the displayed image.
        """

        # Get the index of the selected combo box item
        method_idx = self.method_combobox.currentIndex()

        # Apply bilateral filtering with the selected image, diameter, sigma color, and sigma space
        if method_idx == 1:
            # Choice 1: Bilateral Filtering
            image = cv2.bilateralFilter(self.image, self.diameter, self.sigma_color, 200)
        else:
            # Choice 0: Original Image
            image = self.image

        if self.dilation_request.isChecked():
            image = dilate_image(image)

        if self.compressed_img is not None:
            compressed_h, compressed_w = self.compressed_img.shape
            image = cv2.resize(image, (compressed_w, compressed_h))

        # Update the image label by converting the image to a QImage and setting it as the pixmap for the image label
        image_h, image_w = image.shape
        q_img = QImage(image.data, image_w, image_h, image_w, QImage.Format_Indexed8)
        self.image_label.setPixmap(QPixmap.fromImage(q_img))

        # Update the histogram if the window is displayed
        if self.histogram_window is not None:
            self.histogram_window.update_histogram(image)
            self.histogram_window.show()

    def on_diameter_change(self, diameter):
        """
        Sets the diameter.
        """

        self.diameter = diameter
        self.diameter_label.setText(f"Diameter: {self.diameter}")
        self.update_image()

    def on_sigma_color_change(self, sigma_color):
        """
        Sets the sigmaColor.
        """

        self.sigma_color = sigma_color
        self.sigma_color_label.setText(f"Sigma Color: {self.sigma_color}")
        self.update_image()

    def extract_text(self):
        """
        Run Tesseract OCR using the user-selected image or the same image after going through bilateral filtering
        based on the current diameter, sigma color, and sigma space to extract and display the text on the image.
        """

        # Get the index of the selected combo box item
        method_idx = self.method_combobox.currentIndex()

        if method_idx == 1:
            image = cv2.bilateralFilter(self.image, self.diameter, self.sigma_color, 200)
        else:
            image = self.image

        if self.dilation_request.isChecked():
            image = dilate_image(image)

        # Run Tesseract OCR on the image
        text = pytesseract.image_to_string(image)

        # Display the extracted text
        QMessageBox.information(self, "Text", "Extracted Text: \n\n" + text)

        # Calculate text extraction accuracy if a clean image is provided
        if hasattr(self, 'clean_image') and isinstance(self.clean_image, np.ndarray):
            clean_text = pytesseract.image_to_string(self.clean_image)
            accuracy = calculate_accuracy(text, clean_text)
            QMessageBox.information(self, "Clean Text", "Extracted Clean Text: \n\n" + clean_text)
            QMessageBox.information(self, "Accuracy", "Text Extraction Accuracy: " + str(accuracy) + "%")

    def provide_clean_image(self):
        """
        Allows the user to provide a clean version of the image for accuracy calculation.
        """

        clean_image, clean_file_name = open_image_dialog()
        if clean_image is not None:
            self.clean_image = np.array(clean_image)
            self.clean_label.setText("Clean File: " + clean_file_name)
            if clean_image.shape[0] > max_height and clean_image.shape[1] > max_width:
                clean_image = cv2.resize(clean_image, (max_width, max_height))
            elif clean_image.shape[0] > max_height and clean_image.shape[1] <= max_width:
                clean_image = cv2.resize(clean_image, (clean_image.shape[1], max_height))
            elif clean_image.shape[0] <= max_height and clean_image.shape[1] > max_width:
                clean_image = cv2.resize(clean_image, (max_width, clean_image.shape[0]))

            clean_image_h, clean_image_w = clean_image.shape
            q_img = QImage(clean_image.data, clean_image_w, clean_image_h, clean_image_w, QImage.Format_Indexed8)
            self.clean_image_label.setPixmap(QPixmap.fromImage(q_img))

            QMessageBox.information(self, "Success",
                                    "Valid clean image received! Press \"Extract Text\" for an accuracy calculation!")
        else:
            QMessageBox.warning(self, "Error", "Did not receive a valid clean image!")

    def prepare_to_save(self):
        """
        Obtain the user-selected preprocessed binary image to prepare for saving to a directory.
        """

        image = cv2.bilateralFilter(self.image, self.diameter, self.sigma_color, 200)
        if self.dilation_request.isChecked():
            image = dilate_image(image)
        save_image(self, image)

    def show_histogram(self):
        """
        Shows or hides the histogram with respect to the currently displayed image if the histogram button is pressed.
        """

        # Create the histogram window if it doesn't exist, otherwise remove it
        if self.histogram_window is None:
            self.histogram_window = HistogramWindow(self.image)
        else:
            self.histogram_window = None
        self.update_image()

    def provide_help(self):
        """
        Display help information for the "Bilateral Filtering" program.
        """

        help_text = """How to Enhance and Extract Text from an Image with Bilateral Filtering:

                Step 1: Pass in your noisy image with "Open Image."
                Step 2: Choose "Bilateral Filtering" from the drop-down menu. You will then see the resulting binary image.
                Step 3: Play with the "Diameter" and "Sigma Color" sliders to update the binary image.
                Step 4: Click on "Extract Text" to perform text extraction.
                Step 5: Save the preprocessed binary image if needed.

                Additional Features:

                If you pass in a clean version of your noisy image with "Provide Clean Image" and then press "Extract Text," you can get the extracted text from the noisy and clean counterparts. You will also get a text extraction accuracy from 0%-100%, which represents how well the extracted text from the noisy image resembles the extracted text from the clean image.

                Press "Show/Hide Histogram" to get or remove the histogram of the currently displayed image.
                
                You can also bold the text be clicking the "Bold Text" checkbox.

                BIG Note:
                 
                Your image will be compressed in the application if it is over 450x450. However, saving the binary image will be based on the original dimensions of the given image. The same applies to the extracted text, accuracy calculations, and histograms.  
                """

        QMessageBox.information(self, "Help", help_text)
