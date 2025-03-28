from py_to_adoc.py_to_adoc import DocstringsDocumentCreator


def __main__():
    repo_path = input("Enter repo to convert to documentation:")
    DocstringsDocumentCreator(repo_path).create_docstring_doc()
    print("Done!")


__main__()
