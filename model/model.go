// Package model provides access to the notes database.
// This is an interface to a Sqlite3 database stored in a OneDrive shared directory

package model

import (
	"gorm.io/gorm"
)

type Note struct {
	Filename  string `gorm:"primaryKey"`
	Timestamp string `gorm:"primaryKey"`
	Text      string
}

type Keyword struct {
	gorm.Model
	Mame string
}

type Present struct {
	gorm.Model
	Name string
}

type Speaker struct {
	gorm.Model
	Name string
}
