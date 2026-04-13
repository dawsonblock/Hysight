import "@testing-library/jest-dom";
import { TextDecoder, TextEncoder } from "util";

if (!window.TextEncoder) {
	window.TextEncoder = TextEncoder;
}

if (!globalThis.TextEncoder) {
	globalThis.TextEncoder = TextEncoder;
}

if (!window.TextDecoder) {
	window.TextDecoder = TextDecoder;
}

if (!globalThis.TextDecoder) {
	globalThis.TextDecoder = TextDecoder;
}

if (!window.HTMLElement.prototype.scrollIntoView) {
	window.HTMLElement.prototype.scrollIntoView = jest.fn();
}