/* Accessible source menu; the hidden native select remains the player's contract. */
(function (root) {
  "use strict";
  let nextId = 0;
  const glyph = (doc, paths, cls) => {
    const span = doc.createElement("span");
    span.className = cls;
    span.innerHTML = `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths}</svg>`;
    return span;
  };

  class SourcePicker {
    constructor(host, select) {
      this.host = host;
      this.select = select;
      this.doc = host.ownerDocument;
      this.open = false;
      this.active = 0;
      this.id = `source-picker-${++nextId}`;
      const doc = this.doc;
      const label = doc.createElement("span");
      label.className = "source-label";
      label.id = `${this.id}-label`;
      label.textContent = "Source";
      this.button = doc.createElement("button");
      this.button.type = "button";
      this.button.className = "source-trigger";
      this.button.setAttribute("role", "combobox");
      this.button.setAttribute("aria-haspopup", "listbox");
      this.button.setAttribute("aria-expanded", "false");
      this.button.setAttribute("aria-controls", `${this.id}-options`);
      this.button.setAttribute("aria-labelledby", `${label.id} ${this.id}-value`);
      this.value = doc.createElement("span");
      this.value.id = `${this.id}-value`;
      this.value.className = "source-value";
      this.button.replaceChildren(
        glyph(doc, '<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01"/>', "source-icon"),
        this.value, glyph(doc, '<path d="m6 9 6 6 6-6"/>', "source-chevron"));
      this.menu = doc.createElement("div");
      this.menu.id = `${this.id}-options`;
      this.menu.className = "source-menu";
      this.menu.setAttribute("role", "listbox");
      this.menu.setAttribute("aria-labelledby", label.id);
      this.menu.hidden = true;
      this.options = Array.from(select.children).map((native, index) => {
        const option = doc.createElement("div");
        option.id = `${this.id}-option-${index}`;
        option.className = "source-option";
        option.setAttribute("role", "option");
        option.dataset.value = native.value;
        const name = doc.createElement("span"); name.textContent = native.textContent;
        const dot = doc.createElement("span"); dot.className = "source-dot"; dot.setAttribute("aria-hidden", "true");
        option.replaceChildren(dot, name, glyph(doc, '<path d="m5 12 4 4L19 6"/>', "source-check"));
        option.addEventListener("click", () => this.choose(index));
        option.addEventListener("pointermove", () => { this.active = index; this.highlight(); });
        return option;
      });
      this.menu.replaceChildren(...this.options);
      host.replaceChildren(label, this.button, this.menu);
      this.toggleHandler = () => this.setOpen(!this.open);
      this.keyHandler = (event) => this.keydown(event);
      this.changeHandler = () => this.sync();
      this.outsideHandler = (event) => { if (!host.contains(event.target)) this.setOpen(false); };
      this.button.addEventListener("click", this.toggleHandler);
      this.button.addEventListener("keydown", this.keyHandler);
      select.addEventListener("change", this.changeHandler);
      doc.addEventListener("pointerdown", this.outsideHandler);
      doc.addEventListener("focusin", this.outsideHandler);
      this.sync();
    }

    sync() {
      const selected = this.options.findIndex((option) => option.dataset.value === this.select.value);
      this.active = Math.max(0, selected);
      this.value.textContent = this.select.children[this.active]?.textContent || "Choose source";
      this.options.forEach((option, index) => option.setAttribute("aria-selected", String(index === selected)));
      this.highlight();
    }
    highlight() {
      this.options.forEach((option, index) => option.classList.toggle("is-highlighted", index === this.active));
      if (this.open && this.options[this.active]) this.button.setAttribute("aria-activedescendant", this.options[this.active].id);
      else this.button.removeAttribute("aria-activedescendant");
    }
    setOpen(open) {
      this.open = open;
      this.menu.hidden = !open;
      this.button.setAttribute("aria-expanded", String(open));
      this.host.classList.toggle("is-open", open);
      if (open) this.sync();
      else this.highlight();
    }
    choose(index) {
      const value = this.options[index]?.dataset.value;
      if (!value) return;
      if (value !== this.select.value) {
        this.select.value = value;
        const EventType = this.doc.defaultView?.Event || root.Event;
        this.select.dispatchEvent(new EventType("change", { bubbles: true }));
      }
      this.sync();
      this.setOpen(false);
      this.button.focus();
    }
    keydown(event) {
      const key = event.key;
      if (key === "Escape" && this.open) {
        event.preventDefault(); event.stopPropagation(); this.setOpen(false); return;
      }
      if (key === "Tab") { this.setOpen(false); return; }
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(key)) {
        event.preventDefault();
        if (!this.open) { this.setOpen(true); return; }
        this.active = key === "Home" ? 0 : key === "End" ? this.options.length - 1 :
          (this.active + (key === "ArrowDown" ? 1 : -1) + this.options.length) % this.options.length;
        this.highlight();
      } else if (key === "Enter" || key === " ") {
        event.preventDefault();
        if (this.open) this.choose(this.active); else this.setOpen(true);
      } else if (key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        const match = Array.from(this.select.children).findIndex((option) => option.textContent.toLowerCase().startsWith(key.toLowerCase()));
        if (match >= 0) { event.preventDefault(); this.setOpen(true); this.active = match; this.highlight(); }
      }
    }
    destroy() {
      this.button.removeEventListener("click", this.toggleHandler);
      this.button.removeEventListener("keydown", this.keyHandler);
      this.select.removeEventListener("change", this.changeHandler);
      this.doc.removeEventListener("pointerdown", this.outsideHandler);
      this.doc.removeEventListener("focusin", this.outsideHandler);
      this.host.replaceChildren();
    }
  }
  if (typeof module !== "undefined" && module.exports) module.exports = SourcePicker;
  root.CinemagicSourcePicker = SourcePicker;
})(typeof globalThis !== "undefined" ? globalThis : window);
