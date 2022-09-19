package main

import (
	"html/template"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

func main() {
	// gin.SetMode(gin.ReleaseMode)
	r := gin.Default()

	r.SetFuncMap(template.FuncMap{
		"upper": strings.ToUpper,
	})

	r.Static("/static", "./static")
	r.StaticFile("/favicon.ico", "./static/icons/favicon.ico")

	r.LoadHTMLGlob("templates/*.gohtml")

	r.GET("/terminate", func(c *gin.Context) {
		c.HTML(http.StatusOK, "terminate.gohtml", gin.H{
			"content": "This is the shutdown page",
		})
	})

	r.GET("/editor", func(c *gin.Context) {
		c.HTML(http.StatusOK, "editor.gohtml", gin.H{
			"content": "This is the editor page",
		})
	})

	r.GET("/", func(c *gin.Context) {
		c.HTML(http.StatusOK, "index.gohtml", gin.H{
			"content": "This is an index page...",
		})
	})

	r.GET("/home", func(c *gin.Context) {
		c.HTML(http.StatusOK, "home.gohtml", gin.H{
			"content": "This is the landing page for Noted...",
		})
	})

	r.GET("/about", func(c *gin.Context) {
		c.HTML(http.StatusOK, "about.gohtml", gin.H{
			"content": "This is the about page for Noted...",
		})
	})

	r.GET("/api/list", func(c *gin.Context) {
		jsonData := []byte(`{"notes":"bob-20220902.md,bill-20220909.md"}`)
		c.Data(http.StatusOK, "application/json", jsonData)
	})

	r.GET("/api/updateDatabase", func(c *gin.Context) {
		jsonData := []byte(`{"result": "success", "count": 0}`)
		c.Data(http.StatusOK, "application/json", jsonData)
	})
	err := r.Run("localhost:5823")
	if err != nil {
		return
	}
}
