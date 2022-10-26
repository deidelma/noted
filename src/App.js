// import './App.css'
import React from "react";
import MyEditor from "./components/MyEditor";
import MenuButtons from "./components/MenuButtons";

function App() {
  return (
    <div className="App">
      <div className="container">
        <h2>Noted.  The note taking program.</h2>
        <MenuButtons/>
        <br/>
        <MyEditor />
        <br/>
      </div>
    </div>
  );
}

export default App;
