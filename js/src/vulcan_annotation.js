/**
changed: added max_size
**/

class Choice {
    constructor(category, parent) {
        this.parent = parent;

        // backward compatibility
        this.inputType = category.choiceType || category.inputType;
        this.required = category.required || false;

        this.key = category.key || null;
        this.description = category.description || "";

        this.metadata = category.metadata || {};

        this.is_selected = false;
        this.on_select = null;
        this.data = null;
        this.on_data = null;

        // create children
        if (this.inputType != null && this.inputType !== "text") {
            this.children = [];
            let sum_child_size = 0;
            let max_child_size = 0;
            for (const choice of category.choices) {
                const child = new Choice(choice, this);
                this.children.push(child);
                child.parent = this;
                sum_child_size += child.max_size;
                if (child.max_size > max_child_size) max_child_size = child.max_size;
            }
            if (this.inputType === "mutual") {
                this.max_size = 1 + max_child_size;
            } else {
                this.max_size = 1 + sum_child_size;
            }
        } else {
            this.max_size = 1;
        }
    }

    set_on_data(on_data) {
        this.on_data = on_data;
    }

    set_on_select(on_select) {
        this.on_select = on_select;
    }

    toggle() {
        if (this.is_selected) {
            this.unset();
        } else {
            this.set();
        }
    }

    set(data) {
        this.is_selected = true;
        if (this.inputType === "text") {
            // data = string value
            this.data = data;
        } else if (this.inputType === "mutual") {
            // if data is one of the children's key
            // it will automatically set child
            for (const child of this.children) {
                if (data == null || child.key !== data) {
                    child.unset();
                } else {
                    child.set();
                }
            }
        } else if (this.inputType === "multiple" || this.inputType === "property") {
        } else if (this.inputType == null) {
        }

        if (this.parent != null && this.parent.inputType === "mutual") {
            for (const child of this.parent.children) {
                if (child.is_selected && child !== this) {
                    child.unset();
                }
            }
        }

        if (this.on_select != null) {
            this.on_select(this.is_selected);
        }
        if (this.on_data != null) {
            this.on_data(this.data);
        }
    }

    unset() {
        this.is_selected = false;
        this.data = null;
        if (this.children != null) {
            for (const child of this.children) {
                child.unset();
            }
        }

        if (this.on_select != null) {
            this.on_select(this.is_selected);
        }
    }

    set_bubble(data) {
        this.is_selected = true;
        if (this.inputType == "text") {
            this.data = data;
        } else if (this.inputType == "mutual" && data != null) {
            for (const child of this.children) {
                if (child.key !== data) {
                    child.unset();
                } else {
                    child.set();
                }
            }
        }
        if (this.parent != null) {
            this.parent.set_bubble();
        }
    }

    __compile() {
        if (!this.is_selected) return null;

        if (this.inputType === "text") {
            return { key: this.key, value: this.data };
        } else if (this.inputType === "mutual") {
            for (const child of this.children) {
                if (child.is_selected)
                    return {
                        key: this.key,
                        value: child.__compile(),
                    };
            }
            return null;
        } else if (this.inputType === "multiple" || this.inputType === "property") {
            const data = [];
            for (const child of this.children) {
                if (child.is_selected) {
                    const cc = child.__compile();
                    if (cc != null) data.push(cc);
                }
            }
            return {
                key: this.key,
                value: data,
            };
        }
        if (this.inputType == null) {
            return { key: this.key };
        }
    }

    compile(value_first = false) {
        const data_obj = this.__compile();
        if (value_first) return data_obj.value;
        return data_obj;
    }

    __decompile(annotation) {
        this.is_selected = true;
        if (this.inputType === "text") {
            this.data = annotation.value;
        } else if (this.inputType === "multiple" || this.inputType === "property") {
            for (const item of annotation.value) {
                for (const child of this.children) {
                    if (item.key === child.key) {
                        child.__decompile(item);
                    }
                }
            }
        } else if (this.inputType === "mutual") {
            if (annotation.value != null)
                for (const child of this.children) {
                    if (annotation.value.key === child.key) {
                        child.__decompile(annotation.value);
                        break;
                    }
                }
        } else if (this.inputType == null) {
        }
    }

    __fireevents = function () {
        if (this.on_select != null) this.on_select(true);
        if (this.inputType === "text") {
            if (this.on_data != null) this.on_data(this.data);
        } else if (this.inputType === "multiple" || this.inputType === "property" || this.inputType === "mutual") {
            for (const child of this.children) {
                if (child.is_selected) {
                    child.__fireevents();
                }
            }
        } else if (this.inputType == null) {
        }
    };

    decompile(annotation, value_first = false) {
        this.unset();
        this.__decompile(value_first ? { value: annotation } : annotation);
        this.__fireevents();
    }

    __validate(annotation) {
        if (annotation.key !== this.key) return false;

        if (this.inputType === "text") {
            if (typeof annotation.value === "string" || annotation.value instanceof String) return true;
        } else if (this.inputType === "property") {
            if (!Array.isArray(annotation.value)) return false;
            if (annotation.value.length !== this.children.length) return false;

            for (const c of this.children) {
                let matched = null;
                for (const item of annotation.value) {
                    if (item.key === c.key) {
                        matched = item;
                    }
                }
                if (matched == null || !c.__validate(matched)) return false;
            }
        } else if (this.inputType === "multiple") {
            if (!Array.isArray(annotation.value)) return false;
            // check required
            for (const c of this.children) {
                if (c.required) {
                    let matched = null;
                    for (const item of annotation.value) {
                        if (item.key === c.key) {
                            matched = item;
                        }
                    }
                    if (matched == null || !c.__validate(matched)) return false;
                }
            }
            // check has key
            for (const item of annotation.value) {
                let matched = null;
                for (const c of this.children) {
                    if (item.key === c.key) {
                        matched = c;
                    }
                }
                if (matched == null || !matched.__validate(item)) return false;
            }
            // To do: check duplication?
        } else if (this.inputType === "mutual") {
            if (annotation.value == null || annotation.value.key == null) return false;
            for (const child of this.children) {
                if (annotation.value.key === child.key) {
                    return child.__validate(annotation.value);
                }
            }
        } else if (this.inputType == null) {
        }

        return true;
    }

    validate(annotation, value_first = false) {
        if (value_first) return this.__validate({ key: null, value: annotation });
        return this.__validate(annotation);
    }

    get_compile_errors() {
        // if this node.get_compile_errors is called, meaning we expected this node to be selected.

        const errors = [];

        if (!this.is_selected) {
            errors.push({
                node: this,
                error: this.inputType === "text" ? -2 : -1,
            });
        } else {
            if (this.inputType === "property") {
                for (const c of this.children) {
                    errors.push(...c.get_compile_errors());
                }
            } else if (this.inputType === "multiple") {
                // check required
                for (const c of this.children) {
                    if (c.required || c.is_selected) {
                        errors.push(...c.get_compile_errors());
                    }
                }
            } else if (this.inputType === "mutual") {
                let match_count = 0;
                for (const c of this.children) {
                    if (c.is_selected) {
                        errors.push(...c.get_compile_errors());
                        match_count += 1;
                    }
                }
                if (match_count == 0 || match_count > 1) {
                    errors.push({
                        node: this,
                        error: -3,
                    });
                }
            } else if (this.inputType === "text") {
                if (!(typeof this.data === "string" || this.data instanceof String)) {
                    errors.push({
                        node: this,
                        error: -2,
                    });
                }
            } else if (this.inputType == null) {
            }
        }

        return errors;
    }

    static interpret_error(error) {
        switch (error) {
            case -1:
                return "The required field is not selected.";
            case -2:
                return "Value of the text field is not filled.";
            case -3:
                return "The mutual field is not selected or over selected.";
            default:
                return "Unknown error";
        }
    }

    static __querySelector(annotation, tokens) {
        let parts = tokens[0].split(".");

        if (parts[0] === ">") {
            tokens = tokens.slice(1);
            parts = tokens[0].split(".");
            if (parts[0] !== annotation.key) {
                return null;
            }
        }

        if (annotation.key === parts[0] || parts[0] === "*") {
            tokens = tokens.slice(1);
            if (tokens.length === 0) {
                if (parts.length === 1) {
                    return annotation.value == null ? true : annotation.value;
                } else if (parts[1] === "key") {
                    return annotation.key;
                }
            }
        }

        if (Array.isArray(annotation.value)) {
            for (const child of annotation.value) {
                const result = Choice.__querySelector(child, tokens);
                if (result != null) return result;
            }
        } else if (annotation.value != null && annotation.value.constructor === Object) {
            return Choice.__querySelector(annotation.value, tokens);
        }
        return null;
    }

    static querySelector(annotation, selector, value_first = false) {
        // topic complaint topic.description
        const tokens = selector.split(" ");
        if (value_first) return Choice.__querySelector({ key: null, value: annotation }, tokens);
        return Choice.__querySelector(annotation, tokens);
    }

    querySelector(annotation, selector, value_first = false) {
        // call static method
        return Choice.querySelector(annotation, selector, value_first);
    }

    __queryMetadata(tokens) {
        let parts = tokens[0].split(".");

        if (parts[0] === ">") {
            tokens = tokens.slice(1);
            parts = tokens[0].split(".");
            if (parts[0] !== this.key) {
                return null;
            }
        }

        if (this.key === parts[0] || parts[0] === "*") {
            tokens = tokens.slice(1);
            if (tokens.length === 0) {
                if (parts.length === 1) {
                    return this;
                } else if (parts[1] === "data") {
                    return this.inputType == null ? this.is_selected : this.data;
                } else if (parts[1] === "description") {
                    return this.description;
                } else if (parts[1] === "key") {
                    return this.key;
                } else if (parts[1] === "inputType") {
                    return this.inputType;
                }
            }
        }

        if (Array.isArray(this.children)) {
            for (const c of this.children) {
                const result = c.__queryMetadata(tokens);
                if (result != null) return result;
            }
        }
        return null;
    }

    queryMetadata(selector) {
        const tokens = selector.split(" ");
        return this.__queryMetadata(tokens);
    }

    static checkAnnotation(node, parentPath = '', internalKeyCounter = 0) {
        // input: JavaScript object representing the annotation
        // output: an object with keys: 'errors' (array of errors), 'warnings' (array of warnings), 'revised_node' (revised annotation object)
        return checkAnnotation(node, parentPath, internalKeyCounter);
    }

}

Annotation_logic = Choice;
