/**
 * i18n 前端工具 (P1-04)
 * 用法: t("papers.list.title") → "Paper List" (en) / "试卷列表" (zh)
 * 语言检测: URL query `?lang=en` → cookie `lang` → 浏览器语言
 */

(function () {
    'use strict';

    var localeData = {};
    var currentLang = 'zh';

    // 检测语言
    function detectLang() {
        var params = new URLSearchParams(window.location.search);
        if (params.get('lang')) return params.get('lang');
        var cookie = document.cookie.match(/(^|;\s*)lang=([^;]*)/);
        if (cookie) return cookie[2];
        var navLang = (navigator.language || '').slice(0, 2);
        if (navLang === 'en') return 'en';
        return 'zh';
    }

    // 加载 locale JSON
    function loadLocale(lang, callback) {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/locales/' + lang + '.json', true);
        xhr.onload = function () {
            if (xhr.status === 200) {
                try {
                    localeData = JSON.parse(xhr.responseText);
                    currentLang = lang;
                } catch (e) {
                    localeData = {};
                }
            }
            if (callback) callback();
        };
        xhr.onerror = function () {
            if (callback) callback();
        };
        xhr.send();
    }

    /**
     * 翻译函数
     * @param {string} key — 如 "papers.list.title"
     * @param {object} params — 可选插值参数，如 {title: "试卷A"}
     * @returns {string}
     */
    window.t = function (key, params) {
        var val = localeData[key] || key;
        if (params) {
            for (var k in params) {
                val = val.replace('{' + k + '}', params[k]);
            }
        }
        return val;
    };

    /**
     * 设置语言（刷新页面）
     */
    window.setLang = function (lang) {
        document.cookie = 'lang=' + lang + ';path=/;max-age=31536000';
        window.location.reload();
    };

    /**
     * 获取当前语言
     */
    window.getLang = function () { return currentLang; };

    // 自动检测并加载
    var detected = detectLang();
    loadLocale(detected, function () {
        // locale 加载完成后，触发自定义事件
        var event = new CustomEvent('localeReady', { detail: { lang: currentLang } });
        document.dispatchEvent(event);
    });
})();
