import React from 'react'
import MonacoEditor from '@monaco-editor/react'
import { MonacoMarkdownExtension } from 'monaco-markdown';

class MyEditor extends React.Component{

    constructor(props){
        super(props);
        this.state = {
            code: "# Some code",
        };
    }

    editorDidMount(editor, monaco){
        const extension = new MonacoMarkdownExtension();
        console.log('editorDidMount', editor);
        extension.activate(editor);
        editor.getModel().updateOptions({tabSize: 2})
        editor.focus();
    }


    onChange(newValue, e){
        console.log('onChange', newValue, e);
    }

    render(){
        const code = this.state.code;
        const options = {
            minimap: {
                enabled: false,
            },
            fontSize: 16,
            lineNumbers: 'on',
        };

        return(
            <MonacoEditor
                language='markdown'
                theme='default'
                value={code}
                options={options}
                onChange={this.onChange}
                onMount={this.editorDidMount}
                height='35vh'
            />
        );
    }
}

export default MyEditor;