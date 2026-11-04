import { useEffect } from "react";

const LEAVE_MESSAGE = "You have unsaved answers on this page. Leave without saving?";

// Warns before a reload, tab close, or in-app link would drop unsaved answers.
export function useUnsavedChangesGuard(isDirty: boolean) {
  useEffect(() => {
    if (!isDirty) {
      return;
    }
    function warnBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
    }
    function confirmLinkClick(event: MouseEvent) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      const anchor = (event.target as Element | null)?.closest?.("a[href]");
      if (!(anchor instanceof HTMLAnchorElement) || anchor.target === "_blank") {
        return;
      }
      const url = new URL(anchor.href, window.location.href);
      const samePage = url.origin === window.location.origin && url.pathname === window.location.pathname && url.search === window.location.search;
      if (samePage || url.origin !== window.location.origin) {
        return;
      }
      if (!window.confirm(LEAVE_MESSAGE)) {
        event.preventDefault();
        event.stopPropagation();
      }
    }
    window.addEventListener("beforeunload", warnBeforeUnload);
    document.addEventListener("click", confirmLinkClick, true);
    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      document.removeEventListener("click", confirmLinkClick, true);
    };
  }, [isDirty]);
}
