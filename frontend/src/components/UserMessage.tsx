interface MessageProps {
  text: string;
  sender: string;
}

export default function UserMessage({ text, sender }: MessageProps) {
  return (
    <>
      <div className={`bubble ${sender == "user" ? "user-bubble" : "bot-bubble"}`}>
        {text}
      </div>
    </>
  );
}
