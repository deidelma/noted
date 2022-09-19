package main

import (
	. "github.com/stretchr/testify/assert"
	"testing"
	"time"
)

func TestTimestamp(t *testing.T) {
	n := time.Date(2022, time.September, 10, 11, 01, 0, 0, time.UTC)
	s := Timestamp(n)
	Equal(t, "2022-09-10T11:01:00Z", s)
}
