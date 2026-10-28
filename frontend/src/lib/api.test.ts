import { describe, expect, it } from "vitest";
import { roleHomePath } from "./api";

describe("roleHomePath", () => {
  it("maps teacher to docente", () => {
    expect(roleHomePath("teacher")).toBe("/docente");
  });
  it("maps coordinator to docente", () => {
    expect(roleHomePath("coordinator")).toBe("/docente");
  });
  it("maps student to estudiante", () => {
    expect(roleHomePath("student")).toBe("/estudiante");
  });
  it("maps admin to admin", () => {
    expect(roleHomePath("admin")).toBe("/admin");
  });
  it("maps unknown to login", () => {
    expect(roleHomePath("guest")).toBe("/login");
  });
});
