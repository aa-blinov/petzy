import { useEffect, useState } from 'react';

/**
 * The numbers behind the bars, on the screen of the phone that shows the fault.
 *
 * Nothing here is guesswork: the visual viewport's height and pan, the page's own height and scroll,
 * the two shifts the bars use and whether the app thinks a keyboard is up. It is the only way to
 * know what an iPhone does when a form opens, because a headless browser never pans and never shows
 * a keyboard.
 *
 * It appears only when the address carries `?diag=1`, and stays for the rest of the session: a route
 * change drops the query string, and the moment worth reading is on the form, not on the page the
 * address was typed on. A narrow strip at the very top, in the colours of the theme, as if the phone
 * had dropped it down.
 */

const KEY = 'petzy:diag';

type Numbers = {
    vvHeight: number;
    vvTop: number;
    innerHeight: number;
    scrollY: number;
    shift: string;
    shiftTop: string;
    keyboard: boolean;
    headerTop: number | null;
    barBottom: number | null;
    safeTop: string;
};

function read(): Numbers {
    const vv = window.visualViewport;
    const root = document.documentElement;
    const header = document.querySelector('header');
    const bar = document.querySelector('.bottom-tab-bar-container');
    const style = getComputedStyle(root);
    return {
        vvHeight: Math.round(vv ? vv.height : 0),
        vvTop: Math.round(vv ? vv.offsetTop : 0),
        innerHeight: window.innerHeight,
        scrollY: Math.round(window.scrollY),
        shift: style.getPropertyValue('--vv-shift').trim() || '0px',
        shiftTop: style.getPropertyValue('--vv-shift-top').trim() || '0px',
        keyboard: root.classList.contains('keyboard-open'),
        headerTop: header ? Math.round(header.getBoundingClientRect().top) : null,
        barBottom: bar ? Math.round(bar.getBoundingClientRect().bottom) : null,
        safeTop: style.getPropertyValue('--safe-area-top').trim() || '0px',
    };
}

const dash = (value: number | null) => (value === null ? 'нет' : String(value));

export function DiagOverlay() {
    const [seen, setSeen] = useState<Numbers | null>(null);

    useEffect(() => {
        const asked = new URLSearchParams(window.location.search).get('diag') === '1';
        if (asked) sessionStorage.setItem(KEY, '1');
        if (!asked && sessionStorage.getItem(KEY) !== '1') return;
        const timer = window.setInterval(() => setSeen(read()), 250);
        return () => window.clearInterval(timer);
    }, []);

    if (!seen) return null;
    return (
        <div className="diag" role="status" aria-live="off">
            <span>
                экран <b>{seen.innerHeight}</b>
            </span>
            <span>
                видно <b>{seen.vvHeight}</b>
            </span>
            <span>
                панорама <b>{seen.vvTop}</b>
            </span>
            <span>
                прокрутка <b>{seen.scrollY}</b>
            </span>
            <span>
                сдвиг низа <b>{seen.shift}</b>
            </span>
            <span>
                сдвиг верха <b>{seen.shiftTop}</b>
            </span>
            <span>
                шапка <b>{dash(seen.headerTop)}</b>
            </span>
            <span>
                низ полосы <b>{dash(seen.barBottom)}</b>
            </span>
            <span>
                клавиатура <b>{seen.keyboard ? 'да' : 'нет'}</b>
            </span>
            <span>
                запас сверху <b>{seen.safeTop}</b>
            </span>
        </div>
    );
}
