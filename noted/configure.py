""" 
module to allow for creation and update of configuration information
"""

from tkinter import filedialog
import ttkbootstrap as ttk 
from ttkbootstrap.constants import PRIMARY, INFO, OUTLINE, LEFT


if __name__=='__main__':
    root=ttk.Window(themename='darkly')
    b1 = ttk.Button(root, text="Button 1", bootstyle=PRIMARY) # type: ignore
    b1.pack(side=LEFT, padx=5, pady=10)
    b2 = ttk.Button(root, text="Button 2", bootstyle=(INFO, OUTLINE)) # type: ignore
    b2.pack(side=LEFT, padx=5, pady=10)
    folder_selected = filedialog.askdirectory()
    print(folder_selected)
    root.mainloop()