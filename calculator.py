import tkinter as tk

def press(key):
    if key == '=':
        try:
            result = str(eval(display.get()))
            display.delete(0, tk.END)
            display.insert(tk.END, result)
        except Exception:
            display.delete(0, tk.END)
            display.insert(tk.END, "Error")
    elif key == 'C':
        display.delete(0, tk.END)
    else:
        display.insert(tk.END, key)

root = tk.Tk()
root.title("Calculator")
root.resizable(False, False)

display = tk.Entry(root, width=20, font=('Arial', 20), bd=5, justify='right')
display.grid(row=0, column=0, columnspan=4, padx=10, pady=10)

buttons = [
    ('7', 1, 0), ('8', 1, 1), ('9', 1, 2), ('/', 1, 3),
    ('4', 2, 0), ('5', 2, 1), ('6', 2, 2), ('*', 2, 3),
    ('1', 3, 0), ('2', 3, 1), ('3', 3, 2), ('-', 3, 3),
    ('0', 4, 0), ('.', 4, 1), ('C', 4, 2), ('+', 4, 3),
    ('=', 5, 0, 4)
]

for btn in buttons:
    text = btn[0]
    row = btn[1]
    col = btn[2]
    colspan = btn[3] if len(btn) > 3 else 1
    b = tk.Button(root, text=text, width=5, height=2, font=('Arial', 14),
                  command=lambda t=text: press(t))
    b.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=5, pady=5)

for i in range(6):
    root.grid_rowconfigure(i, weight=1)
for j in range(4):
    root.grid_columnconfigure(j, weight=1)

root.mainloop()