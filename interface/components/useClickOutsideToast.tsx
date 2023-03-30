import { useEffect, useRef } from 'react';
import {
  ToastId,
  useToast,
  UseToastOptions,
} from "@chakra-ui/react";

import { successToast, warningToast } from "./Toasts";

export function useClickOutsideToast() {
  const toast = useToast();
  const toastIdRef = useRef<ToastId | undefined>();

  function closeToast() {
    if (toastIdRef.current) {
      toast.close(toastIdRef.current);
    }
  }

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      closeToast();
    };

    window.addEventListener('click', handleClickOutside);
    return () => {
      window.removeEventListener('click', handleClickOutside);
    };
  }, [closeToast]);

  function openToast(toastOptions: UseToastOptions) {
    toastIdRef.current = toast(toastOptions);
  }

  return { toastIdRef, openToast };
}
