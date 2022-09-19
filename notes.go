package main

import (
	"fmt"
	"time"
)

func Timestamp(t time.Time) string {
	return fmt.Sprint(t.Format(time.RFC3339))
}
