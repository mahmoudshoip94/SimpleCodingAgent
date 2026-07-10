class Memory:
    def __init__(self):
        self.last_action = ""
        self.recent_files = []
        self.last_folder = ""
        self.goal = ""
        self.last_output = ""
        self.last_error = ""
        self.last_fix_attempt = ""
        self.step_count = 0
        self.fix_attempts = 0

    def update(self, action="", files=None, folder="", goal="", output="", error="", fix_attempt=""):
        if files is None:
            files = []
        if action:
            self.last_action = action
        if files:
            for file in files:
                if file not in self.recent_files:
                    self.recent_files.append(file)

            # احتفظ بآخر 5 ملفات فقط
            self.recent_files = self.recent_files[-5:]
        if folder:
            self.last_folder = folder

        if goal:
            self.goal = goal

        if output != "":
            self.last_output = output

        if error != "":
            self.last_error = error

        if fix_attempt:
            self.last_fix_attempt = fix_attempt
        self.step_count += 1
        if fix_attempt:
            self.last_fix_attempt = fix_attempt
            self.fix_attempts += 1

    def clear(self):
        self.last_action = ""
        self.recent_files.clear()
        self.last_folder = ""
        self.goal = ""
        self.last_output = ""
        self.last_error = ""
        self.last_fix_attempt = ""
        self.step_count = 0