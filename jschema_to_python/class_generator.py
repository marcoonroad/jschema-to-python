import sys
from jschema_to_python.python_file_generator import PythonFileGenerator
import jschema_to_python.utilities as util

_TYPE_MAPPING = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
}

_KEYWORD_PROPS = {
    "False": True,
    "def": True,
    "if": True,
    "raise": True,
    "None": True,
    "del": True,
    "import": True,
    "return": True,
    "True": True,
    "elif": True,
    "in": True,
    "try": True,
    "and": True,
    "else": True,
    "is": True,
    "while": True,
    "as": True,
    "except": True,
    "lambda": True,
    "with": True,
    "assert": True,
    "finally": True,
    "nonlocal": True,
    "yield": True,
    "break": True,
    "for": True,
    "not": True,
    "class": True,
    "from": True,
    "or": True,
    "continue": True,
    "global": True,
    "pass": True,
}

class ClassGenerator(PythonFileGenerator):
    def __init__(self, class_schema, class_name, code_gen_hints, output_directory):
        super(ClassGenerator, self).__init__(output_directory)
        self.class_schema = class_schema
        self.required_property_names = class_schema.get("required")
        if self.required_property_names:
            self.required_property_names.sort()
        self.class_name = class_name
        self.code_gen_hints = code_gen_hints
        self.file_path = self._make_class_file_path()

    def __del__(self):
        sys.stdout = sys.__stdout__

    def generate(self):
        with open(self.file_path, "w") as sys.stdout:
            self.write_generation_comment()
            self._write_class_declaration()
            self._write_class_description()
            self._write_class_body()

    def _make_class_file_path(self):
        class_module_name = util.class_name_to_private_module_name(self.class_name)
        return self.make_output_file_path(class_module_name + ".py")

    def _write_class_declaration(self):
        parent_type = "object"
        if "type" in self.class_schema and type(self.class_schema["type"]) == str and self.class_schema["type"] in _TYPE_MAPPING:
            parent_type = _TYPE_MAPPING[ self.class_schema["type"] ]
        elif "properties" not in self.class_schema:
            # workaround in case of untyped/dynamic schema objects, such as .NET's dictionaries
            parent_type = "dict"
        else:
            # TODO: handle type unions in schema, where value would be list of type names, so we will need Py3 typings
            pass
        print("import attr")
        print("")
        print("")  # The black formatter wants two blank lines here.
        print("@attr.s")
        print("class " + self.class_name + "(" + parent_type + "):")

    def _write_class_description(self):
        description = self.class_schema.get("description")
        if description:
            print('    """' + description + '"""')
            print("")  # The black formatter wants a blank line here.

    def _write_class_body(self):
        if "properties" not in self.class_schema:
            print("    pass")
            return
        property_schemas = self.class_schema["properties"]
        if not property_schemas:
            print("    pass")
            return

        schema_property_names = sorted(property_schemas.keys())

        # attrs requires that mandatory attributes be declared before optional
        # attributes.
        if self.required_property_names:
            for schema_property_name in self.required_property_names:
                attrib = self._make_attrib(schema_property_name)
                print(attrib)

        for schema_property_name in schema_property_names:
            if self._is_optional(schema_property_name):
                attrib = self._make_attrib(schema_property_name)
                print(attrib)

    def _make_attrib(self, schema_property_name):
        python_property_name = self._make_python_property_name_from_schema_property_name(
            schema_property_name
        )
        if python_property_name in _KEYWORD_PROPS:
            python_property_name = "_" + python_property_name
        attrib = "".join(["    ", python_property_name, " = attr.ib("])
        if self._is_optional(schema_property_name):
            property_schema = self.class_schema["properties"][schema_property_name]
            default_setter = self._make_default_setter(property_schema)
            attrib = "".join([attrib, default_setter, ", "])
        attrib = "".join(
            [attrib, 'metadata={"schema_property_name": "', schema_property_name, '"})']
        )
        return attrib

    def _is_optional(self, schema_property_name):
        return (
            not self.required_property_names
            or schema_property_name not in self.required_property_names
        )

    def _make_default_setter(self, property_schema):
        initializer = self._make_initializer(property_schema)
        return "default=" + str(initializer)

    def _make_initializer(self, property_schema):
        default = property_schema.get("default")
        if default:
            type = property_schema.get("type")
            if type:
                if type == "string":
                    default = (
                        '"' + default + '"'
                    )  # The black formatter wants double-quotes.
                elif type == "array":
                    # It isn't safe to specify a mutable object as a default value,
                    # because all new instances share the same mutable object, and
                    # one of them might mutate it, affecting all future instances!
                    # attr.Factory creates a new value for each instance.
                    default = "attr.Factory(lambda: " + str(default) + ")"
            elif property_schema.get("enum"):
                default = '"' + default + '"'
            return default

        return "None"

    def _make_python_property_name_from_schema_property_name(
        self, schema_property_name
    ):
        hint_key = self.class_name + "." + schema_property_name
        property_name_hint = self._get_hint(hint_key, "PropertyNameHint")
        if not property_name_hint:
            property_name = schema_property_name
        else:
            property_name = property_name_hint["arguments"]["pythonPropertyName"]
        return util.to_underscore_separated_name(property_name)

    def _get_hint(self, hint_key, hint_kind):
        if not self.code_gen_hints or hint_key not in self.code_gen_hints:
            return None

        hint_array = self.code_gen_hints[hint_key]
        for hint in hint_array:
            if hint["kind"] == hint_kind:
                return hint

        return None
