import React from "react";
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { Modal } from "@/components/frontend/Modal";

describe("Modal", () => {
  it("locks scrolling on both body and documentElement while open", () => {
    const prevBodyOverflow = document.body.style.overflow;
    const prevHtmlOverflow = document.documentElement.style.overflow;

    const { unmount } = render(
      <Modal isOpen={true} onClose={() => {}}>
        <div>content</div>
      </Modal>,
    );

    expect(document.body.style.overflow).toBe("hidden");
    expect(document.documentElement.style.overflow).toBe("hidden");

    unmount();

    expect(document.body.style.overflow).toBe(prevBodyOverflow);
    expect(document.documentElement.style.overflow).toBe(prevHtmlOverflow);
  });
});

