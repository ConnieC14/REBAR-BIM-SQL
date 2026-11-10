import { useState } from "react";
import WindowChat from "./components/Window";
import "./App.css";

function App() {
  const [process] = useState("Processing your request...");

  return (
    <>
      <div className="flex w-full h-screen flex-col md:flex-row justify-center items-center">
        <WindowChat
          heading="REBAR"
          placeholder="What do you need?"
          nameID="vimdb"
          process={process}
        />
      </div>
    </>
  );
}

export default App;
