class Token:
    def __init__(
        self,
        token,
        name=None,
        id=None,
        token_account=None,
        holder_address=None,
        amount=None,
        image=None,
        traits=None,
        data_uri=None,
    ):
        self.token = token

        self.name = name
        self.id = id
        self.token_account = token_account
        self.holder_address = holder_address
        self.amount = amount
        self.image = image
        self.traits = traits if traits is not None else {}
        self.data_uri = data_uri
