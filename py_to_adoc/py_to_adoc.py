import os
import ast

from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# region Exclusion

EXCLUDED_PY_FILES = {
    # "docstrings_docs.py",
    "__init__.py",
    "__manifest__.py",
}
EXCLUDED_METHODES = {
    "__init__",
    "__main__",
    # "__getattr__",
    # "__setattr__",
    # "__delitem__",
    # "__getitem__",
    # "__iter__",
    # "__len__",
    # "__setitem__",
}


# endregion

class DocstringsDocumentCreator:
    """Crée un fichier .adoc listant les docstrings des classes, méthodes et fonctions.
    Ajoute aussi les paramètres et leurs types si precisés via Typing.
    """

    output_file = "docstrings_doc.adoc"
    no_docstring = "_No docstring_"

    def __init__(self, module_path: Optional[str], toclevels: Optional[int] = 3, **kwargs):
        if not module_path:
            module_path = os.getcwd()
        self.module_path = module_path
        self.toclevels = toclevels
        self.module_name = module_path.split("/")[-1]
        output_file_path = f"{self.module_path}/{self.output_file}"
        if module_path.endswith("/"):
            output_file_path = f"{self.module_path}{self.output_file}"
        self.output_file_path = output_file_path
        for k, v in kwargs.items():
            setattr(self, k, v)

    def create_docstring_doc(self) -> None:
        """Récupère les infos des fichiers point .py et les transpose dans un .adoc"""
        if os.path.exists(self.output_file_path):
            os.remove(self.output_file_path)
        project_data = self._extract_docstrings_from_project()
        self._write_to_adoc(project_data)

    # region _get

    @staticmethod
    def _get_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
        """Crée la liste des arguments d'une méthode sous forme de texte, ajoute le type si disponible."""
        res = []
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            argument = arg.arg
            if arg.annotation and hasattr(arg.annotation, "id"):
                argument += f" ({arg.annotation.id})"
            res.append(argument)
        return res

    def _get_class_info(self, node: ast.ClassDef) -> Dict[str:any]:
        """Crée un dictionnaire de classe comprenant le docstring et la class d'héritage
        et la clé 'methods' (vide, car remplie plus tard).
        """
        res = dict()
        res[node.name] = {"docstring": ast.get_docstring(node) or self.no_docstring, "methods": {}}
        if node.bases and hasattr(node.bases[0], "attr"):
            res[node.name]["base"] = node.bases[0].attr
        return res

    def _get_function_info(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Dict:
        """Retourne le dictionnaire documentaire de la fonction (docstrings, arguments).
        Une fonction est une méthode qui n'est pas encapsulée dans une class.
        """
        return self._get_method_info(node)

    def _get_method_info(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Dict:
        """Retour le dictionnaire de la méthode (docstrings, arguments)"""
        value = {
            "docstring": ast.get_docstring(node) or self.no_docstring,
            "args": self._get_args(node),
        }
        if hasattr(node, "returns") and hasattr(node.returns, "id"):
            value["returns"] = node.returns.id
        return {node.name: value}

    # endregion

    # region _extract

    def _extract_docstrings_from_project(self) -> Dict[str:any]:
        """Extrait les docstrings de toutes les classes, méthodes et fonctions d'un projet."""
        project_data = defaultdict(lambda: {"classes": {}, "functions": {}})
        for root, _, files in os.walk(self.module_path):
            for file in files:
                if not file.endswith(".py") or file in EXCLUDED_PY_FILES:
                    continue
                py_file_path = os.path.join(root, file)

                classes, functions = self._extract_docstrings_from_file(py_file_path)
                project_data[py_file_path]["classes"].update(classes)
                project_data[py_file_path]["functions"].update(functions)

        return project_data

    def _extract_docstrings_from_file(self, py_file_path: str) -> Tuple[Dict[str:any], Dict[str:any]]:
        """Extrait les classes, méthodes et fonctions avec leurs docstrings d'un fichier Python."""
        with open(py_file_path, "r", encoding="utf-8") as file:
            tree = ast.parse(file.read(), filename=py_file_path)

        classes = dict()
        functions = dict()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.update(self._get_class_info(node))

            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                parent = next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and node in n.body), None)
                if not parent or parent.name not in classes:
                    functions[node.name] = self._get_function_info(node)
                    continue
                classes[parent.name]["methods"].update(self._get_method_info(node))

        return classes, functions

    # endregion

    # region _write

    def _write_to_adoc(self, project_data: Dict) -> None:
        """Enregistre tous les docstrings extraites dans un fichier AsciiDoc."""
        with open(self.output_file_path, "w+", encoding="utf-8") as file:
            file.write(f":toc:\n:sectnums:\n:toclevels: {self.toclevels}\n:toc-title: Code overview\n\n")
            for file_path, content in sorted(project_data.items()):
                if not content["classes"] and not content["functions"]:
                    continue

                file.write(f"== {file_path.split(self.module_name)[-1]}\n\n")

                for class_name, class_data in sorted(content["classes"].items()):
                    self._write_class_section(file, class_name, class_data)
                    for method_name, method_doc in sorted(class_data["methods"].items()):
                        self._write_method_section(file, method_name, method_doc)

                for func_name, func_doc in sorted(content["functions"].items()):
                    if func_name in content["classes"]:
                        continue
                    self._write_function_section(file, func_name, func_doc[func_name])

    def _write_class_section(self, file: any, class_name: str, class_data: Dict) -> None:
        """Écrit les infos de la class (titre, nom, base) dans le fichier .adoc"""
        class_name = self._format_name(class_name)
        complete_name = class_name
        if class_data.get("base"):
            complete_name += f"(_{class_data['base']}_)"
        file.write(f"=== Classe : {complete_name}\n\n{class_data['docstring']}\n\n")

    def _write_method_section(self, file: any, method_name: str, method_doc: Dict) -> None:
        """Écrit les infos de la method (titre, nom, arguments) dans le fichier .adoc"""
        if method_name in EXCLUDED_METHODES and method_doc["docstring"] == self.no_docstring:
            return
        method_name = self._format_name(method_name)
        text_lines = self._format_method_textlines(method_name, method_doc)
        file.writelines("\n".join(text_lines) + "\n\n")

    def _write_function_section(self, file: any, func_name: str, func_doc: Dict) -> None:
        """Écrit les infos de la function (titre, nom, arguments) dans le fichier .adoc"""
        if func_name in EXCLUDED_METHODES and func_doc["docstring"] == self.no_docstring:
            return
        self._write_method_section(
            file,
            func_name,
            func_doc,
        )
        text_lines = self._format_method_textlines(func_name, func_doc)
        text_lines[0] = f"=== Fonction : {func_name}\n"
        file.writelines("\n".join(text_lines) + "\n\n")

    # endregion

    @staticmethod
    def _format_name(name: str) -> str:
        """Formate le nom de la méthode pour qu'elle n'apparaisse pas en italique en .adoc.
        Par exemple __setitem__ apparaitra `_setitem_` en italic.
        Cette méthode cherche à retirer cela en forçant le premier underscore
        """
        if name.startswith("_") and name.endswith("_"):
            name = f"\\{name}"
        return name

    def _format_method_textlines(self, method_name: str, method_doc: Dict) -> List[str]:
        method_name = self._format_name(method_name)
        text_lines = [f"==== {method_name}\n", f"{method_doc['docstring']}"]
        if method_doc.get("args", False):
            text_lines.extend(["\n*@params* :\n"] + [f"* {args}" for args in method_doc["args"]])
        if method_doc.get("returns", False):
            text_lines.append(f"\n*@returns* : {method_doc['returns']}\n")
        return text_lines
