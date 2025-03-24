import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from datetime import datetime
import os
from Views.View_utils import ViewUtils

class UsersView(ctk.CTk):
    def __init__(self, main_window, db_model, user_controller, tab):
        super().__init__()

