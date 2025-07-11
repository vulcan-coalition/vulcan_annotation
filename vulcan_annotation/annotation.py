"""
changed: added max_size
"""


import json
import os
import shortuuid
from .annotation_checking import check_annotation


class Annotation:

    def __init__(self, category, parent = None):
        self.id = shortuuid.uuid()
        self.parent = parent
        self.inputType = category.get('inputType')
        self.required = category.get('required', False)
        self.key = category.get('key')
        self.description = category.get('description', "")
        self.metadata = category.get('metadata')
        self.is_selected = False
        self.on_select = None
        self.data = None
        self.on_data = None

        if self.inputType and self.inputType != "text":
            self.children = []
            sum_child_size = 0
            max_child_size = 0
            for choice in category['choices']:
                child = Annotation(choice, self)
                self.children.append(child)
                child.parent = self
                sum_child_size += child.max_size
                if child.max_size > max_child_size:
                    max_child_size = child.max_size
            if self.inputType == "mutual":
                self.max_size = 1 + max_child_size
            else: # multiple or property
                self.max_size = 1 + sum_child_size
        else:
            self.children = None
            self.max_size = 1


    def set_on_data(self, on_data):
        self.on_data = on_data

    def set_on_select(self, on_select):
        self.on_select = on_select

    def toggle(self):
        if self.is_selected:
            self.unset()
        else:
            self.set()

    def set(self, data=None):
        self.is_selected = True
        if self.inputType == "text":
            self.data = data
        elif self.inputType == "mutual":
            for child in self.children:
                if data is None or child.key != data:
                    child.unset()
                else:
                    child.set()
        if self.parent and self.parent.inputType == "mutual":
            for child in self.parent.children:
                if child.is_selected and child != self:
                    child.unset()
        if self.on_select:
            self.on_select(self.is_selected)
        if self.on_data:
            self.on_data(self.data)

    def unset(self):
        self.is_selected = False
        self.data = None
        if self.children:
            for child in self.children:
                child.unset()
        if self.on_select:
            self.on_select(self.is_selected)


    def set_bubble(self, data=None):
        self.is_selected = True
        if self.inputType == "text":
            self.data = data
        elif self.inputType == "mutual" and data is not None:
            for child in self.children:
                if child.key != data:
                    child.unset()
                else:
                    child.set()
        if self.parent is not None:
            self.parent.set_bubble()


    def __compile(self):
        if not self.is_selected:
            return None
        if self.inputType == "text":
            return { 'key': self.key, 'value': self.data }
        elif self.inputType == "mutual":
            for child in self.children:
                if child.is_selected:
                    return { 'key': self.key, 'value': child.__compile() }
        elif self.inputType in ["multiple", "property"]:
            data = []
            for child in self.children:
                if child.is_selected:
                    cc = child.__compile()
                    if cc is not None:
                        data.append(cc)
            return { 'key': self.key, 'value': data }
        elif self.inputType is None:
            return { 'key': self.key }

    def compile(self, value_first=False):
        data_obj = self.__compile()
        if value_first:
            return data_obj.get('value')
        return data_obj

    def __decompile(self, annotation):
        self.is_selected = True
        if self.inputType == "text":
            self.data = annotation.get('value')
        elif self.inputType in ["multiple", "property"]:
            for item in annotation.get('value'):
                for child in self.children:
                    if item.get('key') == child.key:
                        child.__decompile(item)
        elif self.inputType == "mutual":
            if annotation.get('value') is not None:
                for child in self.children:
                    if annotation.get('value').get('key') == child.key:
                        child.__decompile(annotation.get('value'))
                        break

    def __fireevents(self):
        if self.on_select:
            self.on_select(True)
        if self.inputType == "text":
            if self.on_data:
                self.on_data(self.data)
        elif self.inputType in ["multiple", "property", "mutual"]:
            for child in self.children:
                if child.is_selected:
                    child.__fireevents()

    def decompile(self, annotation, value_first=False):
        self.unset()
        self.__decompile({ 'value': annotation } if value_first else annotation)
        self.__fireevents()


    def __validate(self, annotation):
        if annotation.get('key') != self.key:
            return False

        if self.inputType == "text":
            if isinstance(annotation.get('value'), str):
                return True
        elif self.inputType == "property":
            if not isinstance(annotation.get('value'), list):
                return False
            if len(annotation.get('value')) != len(self.children):
                return False

            for c in self.children:
                matched = None
                for item in annotation.get('value'):
                    if item.get('key') == c.key:
                        matched = item
                if matched is None or not c.__validate(matched):
                    return False
        elif self.inputType == "multiple":
            if not isinstance(annotation.get('value'), list):
                return False
            for c in self.children:
                if c.required:
                    matched = None
                    for item in annotation.get('value'):
                        if item.get('key') == c.key:
                            matched = item
                    if matched is None or not c.__validate(matched):
                        return False
            for item in annotation.get('value'):
                matched = None
                for c in self.children:
                    if item.get('key') == c.key:
                        matched = c
                if matched is None or not matched.__validate(item):
                    return False
        elif self.inputType == "mutual":
            if annotation.get('value') is None or annotation.get('value').get('key') is None:
                return False
            for child in self.children:
                if annotation.get('value').get('key') == child.key:
                    return child.__validate(annotation.get('value'))
        elif self.inputType is None:
            pass

        return True


    def validate(self, annotation, value_first=False):
        # validate the answer against the category
        if value_first:
            return self.__validate({ 'key': None, 'value': annotation })
        return self.__validate(annotation)


    def get_compile_errors(self):
        # return a list of errors
        errors = []
        if not self.is_selected:
            errors.append({
                'node': self,
                'error': -2 if self.inputType == "text" else -1
            })
        else:
            if self.inputType == "property":
                for c in self.children:
                    errors += c.get_compile_errors()
            elif self.inputType == "multiple":
                for c in self.children:
                    if c.required or c.is_selected:
                        errors += c.get_compile_errors()
            elif self.inputType == "mutual":
                match_count = 0
                for c in self.children:
                    if c.is_selected:
                        errors += c.get_compile_errors()
                        match_count += 1
                if match_count == 0 or match_count > 1:
                    errors.append({
                        'node': self,
                        'error': -3
                    })
            elif self.inputType == "text":
                if not isinstance(self.data, str):
                    errors.append({
                        'node': self,
                        'error': -2
                    })
            elif self.inputType is None:
                pass
        return errors
    

    @staticmethod
    def interpret_error(error):
        if error == -1:
            return "The required field is not selected."
        elif error == -2:
            return "Value of the text field is not filled."
        elif error == -3:
            return "The mutual field is not selected or over selected."
        else:
            return "Unknown error"


    @staticmethod
    def __querySelector(annotation, tokens):
        parts = tokens[0].split(".")
        if parts[0] == ">":
            tokens = tokens[1:]
            parts = tokens[0].split(".")
            if parts[0] != annotation["key"]:
                return None

        if annotation["key"] == parts[0] or parts[0] == "*":
            tokens = tokens[1:]
            if len(tokens) == 0:
                if len(parts) == 1:
                    return True if "value" not in annotation else annotation["value"]
                elif parts[1] == "key":
                    return annotation.key

        if "value" in annotation:
            value = annotation["value"]
            if isinstance(value, list):
                for child in value:
                    result = Annotation.__querySelector(child, tokens)
                    if result is not None:
                        return result
            elif isinstance(value, dict):
                return Annotation.__querySelector(value, tokens)

        return None


    @staticmethod
    def querySelector(annotation, selector, value_first=False):
        tokens = selector.split(" ")
        if value_first:
            result = Annotation.__querySelector(
                {"key": None, "value": annotation}, tokens)
        else:
            result = Annotation.__querySelector(annotation, tokens)
        return None if result is None else result


    def __traverse(self, annotation, handler):
        handler(self, annotation)
        if "value" in annotation:
            value = annotation["value"]
            if isinstance(value, list):
                for c in self.children:
                    for child in value:
                        if c.key == child["key"]:
                            c.__traverse(child, handler)
            elif isinstance(value, dict):
                for c in self.children:
                    if c.key == value["key"]:
                        c.__traverse(value, handler)

    def traverse(self, annotation, handler, value_first=False):
        if value_first:
            self.__traverse({"key": None, "value": annotation}, handler)
        else:
            self.__traverse(annotation, handler)

    def get_all_nodes(self):
        nodes = [self]
        for c in self.children:
            nodes += c.get_all_nodes()
        return nodes

    def __queryMetadata(self, tokens):
        parts = tokens[0].split(".")
        if parts[0] == ">":
            tokens = tokens[1:]
            parts = tokens[0].split(".")
            if parts[0] != self.key:
                return None

        if self.key == parts[0] or parts[0] == "*":
            tokens = tokens[1:]
            if len(tokens) == 0:
                if len(parts) == 1:
                    return self
                elif parts[1] == "data":
                    return self.is_selected if self.inputType is None else self.data;
                elif parts[1] == "description":
                    return self.description
                elif parts[1] == "key":
                    return self.key
                elif parts[1] == "inputType":
                    return self.inputType
                elif parts[1] == "metadata":
                    return self.metadata
                elif parts[1] == "required":
                    return self.required
                elif parts[1] == "choices":
                    return self.children

        if isinstance(self.children, list):
            for c in self.children:
                result = c.__queryMetadata(tokens)
                if result is not None:
                    return result

        return None

    def queryMetadata(self, selector):
        tokens = selector.split(" ")
        result = self.__queryMetadata(tokens)
        return None if result is None else result
    
    @staticmethod
    def check_annotation(node, parent_path='', internal_key_counter=0):
        # input: Python dictionary representing the annotation
        # output: a dictionary with keys: 'errors' (list of errors), 'warnings' (list of warnings), 'revised_node' (revised annotation dict)
        return check_annotation(node, parent_path, internal_key_counter)


if __name__ == '__main__':
    va = Annotation({
        "inputType": "multiple",
        "choices": [
        {
            "key": "car",
            "inputType": "mutual",
            "description": "รถ",
            "metadata":
            {
                "a": 1,
                "b":
                {
                    "c": 2
                }
            },
            "choices": [
            {
                "key": "type",
                "inputType": "mutual",
                "description": "ประเภท",
                "choices": [
                {
                    "key": "a",
                    "inputType": "mutual",
                    "description": "รถเก๋ง",
                    "choices": [
                        {
                            "key": "a",
                            "description": "รถเก๋ง 4 ประตู"
                        },
                        {
                            "key": "b",
                            "description": "รถเก๋ง 2 ประตู"
                        }
                    ]
                },
                {
                    "key": "b",
                    "description": "รถตู้"
                }]
            },
            {
                "key": "lp_text",
                "inputType": "text",
                "description": "เลขทะเบียน"
            }]
        },
        {
            "key": "lp",
            "inputType": "property",
            "description": "ป้ายทะเบียน",
            "required": True,
            "choices": [
            {
                "key": "lp_color",
                "description": "มีสี"
            },
            {
                "key": "lp_type",
                "inputType": "mutual",
                "description": "ประเภทป้าย",
                "choices": [
                {
                    "key": "lpr",
                    "description": "ป้ายทะเบียนรถยนต์"
                },
                {
                    "key": "mlpr",
                    "description": "ป้ายทะเบียนรถมอไซด์"
                }]
            }]
        }]
    })

    print("Category max_size", va.max_size)

    print(va.queryMetadata("car a.description"))
    print(va.queryMetadata("a > a.description"))

    va.queryMetadata("lp_text").set_bubble("1234")
    va.queryMetadata("lp_color").set_bubble()
    annotation = va.compile()
    print(json.dumps(annotation, indent=2))

    print(va.querySelector(annotation, "car lp_text"))
    print(Annotation.querySelector(annotation, "lp > lp_color"))

    va.decompile([
            {
                "key": "lp",
                "value": [
                {
                    "key": "lp_color"
                }
                ]
            }
        ], 
        value_first=True)

    errors = va.get_compile_errors()
    for error in errors:
        print(Annotation.interpret_error(error['error']), error['node'].key)

    print(va.validate([
            {
                "key": "lp",
                "value": [
                    {
                        "key": "lp_color"
                    }
                ]
            }
        ], 
        value_first=True)
    )

    print(va.validate([
            {
                "key": "lp",
                "value": [
                    {
                        "key": "lp_color"
                    },
                    {
                        "key": "lp_type",
                        "value": {
                            "key": "lpr"
                        }
                    }
                ]
            }
        ], 
        value_first=True)
    )

