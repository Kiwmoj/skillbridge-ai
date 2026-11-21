"""Matplotlib charts embedded in the desktop interface."""
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class ChartCanvas(FigureCanvas):
    def __init__(self, parent=None, height=3.2):
        self.figure = Figure(figsize=(7, height), dpi=100, facecolor="#151c2b")
        self.axes = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.30, right=0.96, top=0.92, bottom=0.23)
        super().__init__(self.figure)
        self.setParent(parent)

    def style_axes(self):
        self.axes.set_facecolor("#151c2b")
        self.axes.tick_params(colors="#9ba9be", labelsize=9)
        for spine in self.axes.spines.values():
            spine.set_visible(False)
        self.axes.grid(axis="y", color="#263247", linewidth=0.8)
        self.axes.set_axisbelow(True)

    def draw_skill_chart(self, skills):
        self.axes.clear()
        self.style_axes()
        skills = [s for s in skills if s.proficiency is not None]
        if not skills:
            self.axes.text(0.5, 0.5, "Rate a skill to chart it", color="#9ba9be", ha="center", va="center", transform=self.axes.transAxes)
            self.axes.set_axis_off()
        else:
            names = [s.name for s in skills]
            values = [s.proficiency for s in skills]
            targets = [s.target for s in skills]
            y = list(range(len(names)))
            self.axes.barh(y, [100] * len(names), color="#222d42", height=0.62)
            self.axes.barh(y, values, color="#52a5ff", height=0.62, label="Self-reported")
            for i, target in enumerate(targets):
                if target is not None:
                    self.axes.plot([target, target], [i - 0.35, i + 0.35], color="#bc8cff", linewidth=2)
            self.axes.set_yticks(y, names)
            self.axes.invert_yaxis()
            self.axes.set_xlim(0, 100)
            self.axes.set_xlabel("Self-reported proficiency · target marker", color="#9ba9be", fontsize=9)
        self.draw_idle()

    def draw_progress_chart(self, activities):
        self.axes.clear()
        self.figure.subplots_adjust(left=0.15, right=0.96, top=0.92, bottom=0.22)
        self.style_axes()
        stages = ["Beginner", "Intermediate", "Advanced"]
        done, remaining = [], []
        for stage in stages:
            group = [a for a in activities if a.stage == stage]
            done.append(sum(a.status == "Completed" for a in group))
            remaining.append(len(group) - done[-1])
        if not activities:
            self.axes.text(0.5, 0.5, "Complete roadmap activities to see progress", color="#9ba9be", ha="center", va="center", transform=self.axes.transAxes)
            self.axes.set_axis_off()
        else:
            self.axes.bar(stages, done, color="#52a5ff", label="Completed")
            self.axes.bar(stages, remaining, bottom=done, color="#29354a", label="Planned")
            self.axes.set_ylabel("Activities", color="#9ba9be")
            self.axes.legend(loc="upper right", facecolor="#151c2b", edgecolor="#263247", labelcolor="#dbe5f5", fontsize=8)
        self.draw_idle()
