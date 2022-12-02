let READ_ONLY = false;

const editor = monaco.editor.create(document.getElementById("container"), {
  language: "markdown-math",
  value: "",
  minimap: {
    enabled: false,
  },
  fontSize: 16,
//   theme: "vs-dark",
  theme: "default",
  readOnly: "true",
});
require(["MonacoMarkdown"], function (MonacoMarkdown) {
  const extension = new MonacoMarkdown.MonacoMarkdownExtension();
  extension.activate(editor);
});
editor.getModel().setValue(noteBody);

