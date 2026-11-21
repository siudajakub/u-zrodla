import { createDesk } from "./app.js";

const Desk = createDesk(React);
ReactDOM.createRoot(document.getElementById("app")).render(React.createElement(Desk));
