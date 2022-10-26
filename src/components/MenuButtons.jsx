import React from 'react'

class MenuButtons extends React.Component{
  constructor(props) {
    super(props);
    this.state = {};
  }

  newNote() {
    alert("new note");
  }

  findOnDisk() {
    alert("findOnDisk");
  }

  findInDb() {
    alert("findInDb");
  }

  updateDb() {
    alert("updateDb")
  }

  render() {
    return (
      <div>
        <button className="btn btn-primary" onClick={this.newNote}>
          New Note
        </button>
        <button className="btn btn-primary" onClick={this.findOnDisk}>
          Find Note On Disk
        </button>
        <button className="btn btn-primary" onClick={this.findInDb}>
          Find Note In Database
        </button>
        <button className ="btn btn-primary" onClick={this.updateDb}>
          Update Database
        </button>
      </div>
    );
  }
}

export default MenuButtons;
