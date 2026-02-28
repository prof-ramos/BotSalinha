"""
Test data factories for BotSalinha testing.

Provides factory classes for generating test data following
the Factory pattern for consistent, realistic test data.
"""

from typing import Any

from faker import Faker

# Brazilian Portuguese Faker instance
fake = Faker("pt_BR")


class DiscordFactory:
    """
    Factory for Discord-related test data.

    Generates realistic Discord IDs, usernames, guild names, etc.
    """

    @staticmethod
    def user_id() -> str:
        """Generate a realistic Discord user ID."""
        return str(fake.random_int(min=100000000000000000, max=999999999999999999))

    @staticmethod
    def guild_id() -> str:
        """Generate a realistic Discord guild ID."""
        return str(fake.random_int(min=100000000000000000, max=999999999999999999))

    @staticmethod
    def channel_id() -> str:
        """Generate a realistic Discord channel ID."""
        return str(fake.random_int(min=100000000000000000, max=999999999999999999))

    @staticmethod
    def message_id() -> str:
        """Generate a realistic Discord message ID."""
        return str(fake.random_int(min=100000000000000000, max=999999999999999999))

    @staticmethod
    def username() -> str:
        """Generate a realistic Discord username."""
        return fake.user_name()

    @staticmethod
    def guild_name() -> str:
        """Generate a realistic Discord guild name."""
        prefixes = ["Servidor", "Comunidade", "Guilda", "Clube", "Team"]
        topics = ["Direito", "Concursos", "Estudos", "Jurídico", "Legal", "Advocacia"]
        return f"{fake.random_element(prefixes)} de {fake.random_element(topics)} {fake.city()}"

    @staticmethod
    def channel_name() -> str:
        """Generate a realistic Discord channel name."""
        topics = ["geral", "duvidas", "estudos", "concursos", "direito", "jurisprudencia"]
        return fake.random_element(topics)

    @staticmethod
    def message_content() -> str:
        """Generate a realistic Discord message content."""
        return fake.sentence()


class LegalContentFactory:
    """
    Factory for legal content test data.

    Generates questions, responses, and citations related to Brazilian law.
    """

    QUESTIONS = [
        "Qual é o prazo de prescrição para uma ação trabalhista?",
        "Quais são os requisitos para ingressar no cargo de procurador?",
        "Explique a diferença entre crime doloso e culposo.",
        "Qual é a base de cálculo do ICMS?",
        "Quais são os direitos fundamentais previstos na Constituição?",
        "O que é jurisprudência e qual o seu valor?",
        "Explique o princípio da dignidade da pessoa humana.",
        "Quais são os tipos de penas previstas no Código Penal?",
        "O que é coisa julgada?",
        "Explique o princípio da legalidade no Direito Administrativo.",
        "Quais são os tipos de provas no Processo Civil?",
        "O que é o princípio do contraditório?",
        "Explique a competência federal e estadual.",
        "Quais são os requisitos da responsabilidade civil?",
        "O que é habeas corpus?",
    ]

    RESPONSES = [
        "De acordo com a Constituição Federal de 1988, o prazo é de 5 anos para ações trabalhistas, conforme artigo 7º, inciso XXIX.",
        "Os requisitos incluem bacharelado em Direito, reconhecido pela MEC, aprovação em concurso público e posse no cargo.",
        "Crime doloso ocorre quando há intenção do agente (dolo), enquanto crime culposo resulta de negligência, imprudência ou imperícia.",
        "A base de cálculo do ICMS é o valor da operação, conforme artigo 13 da Lei Complementar 87/1996 (Lei Kandir).",
        "Os direitos fundamentais estão previstos no artigo 5º da Constituição Federal, com mais de 70 incisos.",
        "A jurisprudência é o conjunto de decisões reiteradas dos tribunais sobre uma matéria, tendo função de orientar decisões.",
        "O princípio da dignidade da pessoa humana está no artigo 1º, inciso III da Constituição, sendo fundamento da República.",
        "O Código Penal prevê penas privativas de liberdade (reclusão, detenção), restritivas de direitos e multa.",
        "Coisa julgada é a qualidade que torna imutável e indiscutível a decisão judicial transitada em julgado.",
        "O princípio da legalidade estabelece que a Administração Pública só pode agir conforme a lei determina.",
    ]

    CITATIONS = (
        "Constituição Federal de 1988, art. 5º",
        "Código Civil, art. 186",
        "Código Penal, art. 13",
        "CLT, art. 7º",
        "Código de Processo Civil, art. 319",
        "Lei 8.112/1990 (Estatuto do Servidor Público)",
        "Súmula Vinculante 11 do STF",
        "Lei Complementar 87/1996 (Lei Kandir)",
    )

    @classmethod
    def legal_question(cls) -> str:
        """Generate a realistic legal question."""
        return fake.random_element(cls.QUESTIONS)

    @classmethod
    def legal_response(cls) -> str:
        """Generate a realistic legal response."""
        return fake.random_element(cls.RESPONSES)

    @staticmethod
    def message_id() -> str:
        """Generate a realistic Discord message ID."""
        return str(fake.random_int(min=100000000000000000, max=999999999999999999))

    @classmethod
    def complex_legal_response(cls) -> str:
        """Generate a multi-paragraph legal response."""
        paragraphs = [
            fake.random_element(cls.RESPONSES),
            "Essa posição é corroborada pela jurisprudência dos tribunais superiores.",
            f"Conforme {fake.random_element(cls.CITATIONS)}.",
        ]
        return "\n\n".join(paragraphs)


class ConversationFactory:
    """
    Factory for conversation test data.

    Creates conversation objects and data structures.
    """

    @staticmethod
    def create_conversation_data(
        user_id: str | None = None,
        guild_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create conversation creation data.

        Args:
            user_id: Optional user ID (generated if not provided)
            guild_id: Optional guild ID (generated if not provided)
            channel_id: Optional channel ID (generated if not provided)

        Returns:
            Dictionary with conversation data
        """
        return {
            "user_id": user_id or DiscordFactory.user_id(),
            "guild_id": guild_id or DiscordFactory.guild_id(),
            "channel_id": channel_id or DiscordFactory.channel_id(),
        }

    @staticmethod
    def create_conversation_with_messages(
        message_count: int = 3,
    ) -> dict[str, Any]:
        """
        Create a complete conversation with messages.

        Args:
            message_count: Number of message pairs to generate

        Returns:
            Dictionary with conversation and messages data
        """
        user_id = DiscordFactory.user_id()
        guild_id = DiscordFactory.guild_id()
        channel_id = DiscordFactory.channel_id()

        messages = []
        for _i in range(message_count):
            # User message
            messages.append(
                {
                    "role": "user",
                    "content": LegalContentFactory.legal_question(),
                    "discord_message_id": DiscordFactory.message_id(),
                }
            )
            # Assistant response
            messages.append(
                {
                    "role": "assistant",
                    "content": LegalContentFactory.legal_response(),
                    "discord_message_id": None,
                }
            )

        return {
            "conversation": {
                "user_id": user_id,
                "guild_id": guild_id,
                "channel_id": channel_id,
            },
            "messages": messages,
        }


class MessageFactory:
    """
    Factory for message test data.

    Creates message objects and data structures.
    """

    @staticmethod
    def create_message_data(
        conversation_id: str,
        role: str = "user",
        content: str | None = None,
        discord_message_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create message creation data.

        Args:
            conversation_id: Conversation ID for the message
            role: Message role (user/assistant/system)
            content: Message content (generated if not provided)
            discord_message_id: Optional Discord message ID

        Returns:
            Dictionary with message data
        """
        if content is None:
            if role == "user":
                content = LegalContentFactory.legal_question()
            elif role == "assistant":
                content = LegalContentFactory.legal_response()
            else:
                content = fake.sentence()

        if discord_message_id is None and role == "user":
            discord_message_id = DiscordFactory.message_id()

        return {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "discord_message_id": discord_message_id,
        }

    @staticmethod
    def create_user_message(
        conversation_id: str,
        question: str | None = None,
    ) -> dict[str, Any]:
        """Create a user message with legal question."""
        return MessageFactory.create_message_data(
            conversation_id=conversation_id,
            role="user",
            content=question or LegalContentFactory.legal_question(),
        )

    @staticmethod
    def create_assistant_message(
        conversation_id: str,
        response: str | None = None,
    ) -> dict[str, Any]:
        """Create an assistant message with legal response."""
        return MessageFactory.create_message_data(
            conversation_id=conversation_id,
            role="assistant",
            content=response or LegalContentFactory.legal_response(),
        )


__all__ = [
    "DiscordFactory",
    "LegalContentFactory",
    "ConversationFactory",
    "MessageFactory",
    "fake",
]
