package model

import (
	. "github.com/stretchr/testify/assert"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"testing"
	"time"
)

func TestGormWorks(t *testing.T) {
	Equal(t, true, true)

	db, err := gorm.Open(sqlite.Open("test.db"), &gorm.Config{})
	Equal(t, nil, err)

	err = db.AutoMigrate(&Note{})
	Equal(t, nil, err)

	db.Create(&Note{Filename: "bob.md", Timestamp: time.Now().UTC().Format(time.RFC3339), Text: "text"})

	var note Note
	db.First(&note, "filename = ?", "bob.md")
	Equal(t, "text", note.Text)

}
