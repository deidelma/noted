/// provides the specific javascript routines for the display endpoint

const create_editor = (elementName) => {
  let editor = monaco.editor.create(document.getElementById(elementName), {
    language: "markdown-math",
    value: "",
    minimap: {
      enabled: false,
    },
    fontSize: 16,
    //   theme: "vs-dark",
    theme: "default",
    // readOnly: "true",
    lineNumbers: "on",
    dragAndDrop: "true",
    autoClosingQuotes: "beforeWhitespace",
    autoClosingBrackets: "beforeWhitespace",
    suggestSelection: "recentlyUsed",
  });
  require(["MonacoMarkdown"], function (MonacoMarkdown) {
    const extension = new MonacoMarkdown.MonacoMarkdownExtension();
    extension.activate(editor);
  });
  return editor;
};

// display_note
//
// initializes the editor component
//
// parameters:
//  editor: MonacoEditor
//  noteBody: String
//  readOnly: bool
//
const display_note = (editor, noteBody, readOnly) => {
  editor.getModel().setValue(noteBody);
  editor.updateOptions({ readOnly: readOnly });
};
