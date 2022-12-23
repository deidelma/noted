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

// find_notes_by_stem
//
// Given the stem to use as a search_string and the element name
// generates a list of links to files on the disk that start with the stem.
//
// parameters:
//  stem: string The stem to search, e.g. lesley, p7
//  elementName: string The id of the element to inject the links into
//
const find_notes_by_stem = function (stem, elementName) {
  // call server to find the notes that match the stem
  let data = { search_string: stem };
  $.post(`${SERVER_URL}/api/stem`, data, function (data) {
    let notesList = String(data.notes).split(",");
    let e = document.getElementById(elementName);
    let lines = [`<div><br/>Found ${notesList.length} notes<br/>`];
    lines.push(`<ul class='list-group' style="list-style:none; list-style-type:none;">`);
    for (const item of notesList) {
      let filename = item.trim();
      let link = `<a href=${SERVER_URL}/display?filename=${encodeURIComponent(filename)}>${filename}</a>`;
      lines.push(`<li class="list-group-item">` + link + `<li>`);
    }
    lines.push("</ul></div>");
    e.innerHTML = lines.join("\n");
  });
};

// get stem based on the prefix of filename
const get_stem = (filename) => {
  const filename_re = /^(.*[\/\\])*([a-zA-Z]+)(\-\d+)*/;
  let items = filename.match(filename_re);

  let stem = items[2];
  return stem;
};
