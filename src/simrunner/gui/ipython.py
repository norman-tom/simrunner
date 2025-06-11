import ipywidgets as widgets
from IPython.display import display


class ViewController(widgets.HBox):
    def __init__(self):
        super().__init__()
        self.layout = widgets.Layout(width="500px", height="35px", justify_content="space-around")
        self.run_id = widgets.Label(value="Run ID:", layout=widgets.Layout(width="350px", height="30px", resize="none"))

        button_layout = widgets.Layout(width="100px", height="30px", border="1px solid black")
        self.stop_button = widgets.Button(description="Stop", layout=button_layout)
        self.play_pause_button = widgets.Button(description="Pause", layout=button_layout)
        self.state_box = widgets.Label(
            value="Running", layout=widgets.Layout(width="100px", height="30px", resize="none")
        )

        self.stop_button.on_click(self.stop_button_clicked)
        self.play_pause_button.on_click(self.play_pause_button_clicked)

        self.children = [self.run_id, self.stop_button, self.play_pause_button, self.state_box]

        display(self)

    # Define the button click handlers
    def stop_button_clicked(self, button):
        self.state_box.value = "Terminated"

    def pause_button_clicked(self):
        self.play_pause_button.description = "Play"
        self.state_box.value = "Paused"

    def play_button_clicked(self):
        self.play_pause_button.description = "Pause"
        self.state_box.value = "Running"

    def play_pause_button_clicked(self, button):
        if self.play_pause_button.description == "Pause":
            self.pause_button_clicked()
        else:
            self.play_button_clicked()

    def set_run_id(self, run_id):
        self.run_id.value = f"{run_id}"
