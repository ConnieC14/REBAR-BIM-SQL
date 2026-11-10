import { useState } from "react";
import Form from "./Form";
import UserMessage from "./UserMessage";
import BotLoader from "./Loader";

interface Props {
  heading: string;
  placeholder: string;
  nameID: string;
  process: string;
}

function WindowChat({ heading, placeholder, nameID, process }: Props) {
  const [messages, setMessages] = useState<{ text: string; sender: string }[]>([]);

  const addMessage = (text: string, sender: string) => {
    setMessages((prevMessages) => [...prevMessages, { text, sender }]);
  };

  return (
    <>
      <div className="w-full max-w-3xl h-[750px] flex flex-col justify-between bg-white rounded-lg shadow-lg overflow-hidden">
        <div className="flex items-center bg-blue-600 p-8 text-white">
          <h1 className="text-xl font-semibold">{heading}</h1>
        </div>

        <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
          {messages.map((msg, index) => (
            <div
              className={`w-full max-w-sm mb-2 ${
                msg.sender === "user" ? "ml-auto" : "mr-auto"
              }`}
              key={index}
            >
              <UserMessage key={index} text={msg.text} sender={msg.sender} />
            </div>
          ))}
        </div>

        {/* Loader is shown when processing */}
        {process && <BotLoader process={process} />}

        {/* Form for user input */}
        <Form
          placeholder={placeholder}
          nameID={nameID}
          addMessage={addMessage}
        />
      </div>
    </>
  );
}

export default WindowChat;
