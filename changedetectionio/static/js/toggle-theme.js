// Modified 2026 for the simplified (academic) fork of changedetection.io - optional features removed, see CHANGES.md
/**
 * @file
 * Toggles theme between light and dark mode.
 */
$(document).ready(function () {

    $(".toggle-light-mode").on("click", function () {
        // "auto" (no cookie yet) follows the device setting, so flip whatever is currently shown
        const state = $("html").attr("data-darkmode");
        const isDark = state === "true" ||
            (state === "auto" && window.matchMedia("(prefers-color-scheme: dark)").matches);
        $("html").attr("data-darkmode", !isDark);
        setCookieValue(!isDark);
    });

    const setCookieValue = (value) => {
        document.cookie = `css_dark_mode=${value};max-age=31536000;path=/`
    }

    setInterval(function () {
        $('body').toggleClass('spinner-active', $.active > 0);
    }, 2000);

});
