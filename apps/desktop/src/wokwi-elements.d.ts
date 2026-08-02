import type { DetailedHTMLProps, HTMLAttributes } from "react";

type WokwiElementProps = DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
  color?: string;
  label?: string;
  value?: boolean;
};

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "wokwi-led": WokwiElementProps;
      "wokwi-pushbutton": WokwiElementProps;
      "wokwi-slide-switch": WokwiElementProps;
      "wokwi-potentiometer": WokwiElementProps;
      "wokwi-servo": WokwiElementProps;
      "wokwi-ssd1306": WokwiElementProps;
    }
  }
}

export {};
