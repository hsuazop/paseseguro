def aplicar_bootstrap(form):
    for field in form.fields.values():
        widget = field.widget
        if widget.__class__.__name__ in {"CheckboxInput", "RadioSelect"}:
            css = "form-check-input"
        elif widget.__class__.__name__ == "SelectMultiple":
            css = "form-select"
        elif widget.__class__.__name__ == "Select":
            css = "form-select"
        else:
            css = "form-control"
        widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()
    return form
