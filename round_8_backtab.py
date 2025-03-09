import pandas as pd
import random
from itertools import permutations, product

# CONFIG
year = 2025
cutoff_point = 20 # at what point you start to cut off
cutoff_threshold = 50 # max loss permitted at cutoff point
max_search_len = 50 # max length for earch to go on
make_empty_files = True
initialise_directory = f"data/{year}"
r7_filename = f"r7_output_{year}.txt"



orders = [order for order in permutations([0, 1, 2, 3])]

class Team:
    def __init__(self, name, known):
        self.name = name
        self.known = known
        self.r7_est = 0
        self.r8_est = 0
        self.r7_room = None
        self.r8_room = None
        self.r9_room = None
        self.r7_poss = []

    def __str__(self):
        return self.name


class Room:
    def __init__(self, teams, round_num):
        self.teams = teams
        self.round_num = round_num

    def set_order(self, order):
        for team, score in zip(self.teams, order):
            if self.round_num == 7:
                team.r7_est = score
            if self.round_num == 8:
                team.r8_est = score

    def __str__(self):
        room_string = f"ROOM (round {self.round_num})"
        for team in self.teams:
            room_string += f"\n\t{team.r7_est} {team.r8_est} {team.name}"
        return room_string


def initialise(directory):
    """
    Returns:
    1. teams (dict): Team objects, key is name
    2. r7_rooms (list): list of Room objects
    3. r8_rooms (list): list of Room objects
    4. r9_rooms (list): list of Room objects
    """
    # Make the teams
    standings = pd.read_csv(f"{directory}/standings.txt", sep="\t")
    teams = {}
    for _, row in standings.iterrows():
        teams[row["team"]] = Team(row["team"], row["points"])

    # Then get r7 info
    r7_draw = pd.read_csv(f"{directory}/r7_draw.txt", sep="\t")
    r7_rooms = []
    for _, row in r7_draw.iterrows():
        room_teams = [teams[name] for name in row]
        room = Room(room_teams, 7)
        r7_rooms.append(room)
        for team in room_teams:
            team.r7_room = room

    # Then get r8 info
    r8_draw = pd.read_csv(f"{directory}/r8_draw.txt", sep="\t")
    r8_rooms = []
    for _, row in r8_draw.iterrows():
        room_teams = [teams[name] for name in row]
        room = Room(room_teams, 8)
        r8_rooms.append(room)
        for team in room_teams:
            team.r8_room = room

    # Then get r9 info
    r9_draw = pd.read_csv(f"{directory}/r9_draw.txt", sep="\t")
    r9_rooms = []
    for _, row in r9_draw.iterrows():
        room_teams = [teams[name] for name in row]
        room = Room(room_teams, 9)
        r9_rooms.append(room)
        for team in room_teams:
            team.r9_room = room

    reset_results(r7_rooms, r8_rooms)

    return teams, r7_rooms, r8_rooms, r9_rooms


def reset_results(r7_rooms, r8_rooms):
    """
    Does what it says on the tin: before running a simulation it chooses
    a random point in parameter space whence to begin
    """
    for room in r7_rooms:
        for team in room.teams:
            team.r7_est = random.choice([0, 1, 2, 3])
    for room in r8_rooms:
        for team in room.teams:
            team.r8_est = random.choice([0, 1, 2, 3])


def get_oob_loss(round, round_room, outside_scores):
    """
    Get the number of teams whose scores are between room max and min
    round (int): round number
    round_room (Room): the room being scored
    outside_scores (Series): other scores in the draw
    NOTE: might need to adjust for very extreme rooms, e.g., the 66666543 case
    """
    if round == 8:
        team_scores = [team.known + team.r7_est for team in round_room.teams]
    if round == 9:
        team_scores = [team.known + team.r7_est + team.r8_est
                        for team in round_room.teams]
    room_min, room_max = min(team_scores), max(team_scores)
    res = ((outside_scores > room_min) & (outside_scores < room_max)).sum()
    return res


def get_pullup_loss(round, teams, round_rooms):
    """
    Max pullups for a given bracket is 3
    This penalises for each pullup beyond that
    """
    pullup_dict = dict(zip(np.arange(28), [0]*28))
    for room in round_rooms:
        if round == 8:
            room_scores = [team.known + team.r7_est for team in room.teams]
        if round == 9:
            room_scores = [team.known + team.r7_est + team.r8_est
                            for team in room.teams]
        room_max = max(room_scores)
        for team in room.teams:
            if round == 8:
                team_score = team.known + team.r7_est
            if round == 9:
                team_score = team.known + team.r7_est + team.r8_est
            if team_score < room_max:
                pullup_dict[team_score] += 1
    pullup_loss = sum([max(0, val - 3) for val in pullup_dict.values()])
    return pullup_loss * 2


def choose_order_for_r7_room(teams, r7_room, r8_rooms):
    """
    This is for the handful of r7 rooms for which the result isn't certain
    This calculates loss over both rounds 8 and 9
    Another thing of note: it allows for multiple teams to get the same
    result in the round. However, that is penalised with "collision loss",
    which is the number of such collisions.
    """
    orders = [o for o in product(
        r7_room.teams[0].r7_poss,
        r7_room.teams[1].r7_poss,
        r7_room.teams[2].r7_poss,
        r7_room.teams[3].r7_poss,
    )]
    if len(orders) == 1:
        r7_room.set_order(orders[0])
        return

    # Do infrastructure before loop to save calculations
    team_r8_room = [team.r8_room for team in r7_room.teams
                    if team.r8_room is not None]
    team_r9_room = [team.r8_room for team in r7_room.teams
                    if team.r9_room is not None]
    scores_out_r8_rooms = []
    scores_out_r9_rooms = []
    for room in team_r8_room:
        if room is None:
            scores_out_r8_rooms.append(None)
        else:
            scores = pd.Series([team.known + team.r7_est
                                for team in teams.values()
                                if team not in r7_room.teams
                                and team.r8_room is not None])
            scores_out_r8_rooms.append(scores)
    for room in team_r9_room:
        if room is None:
            scores_out_r9_rooms.append(None)
        else:
            scores = pd.Series([team.known + team.r7_est + team.r8_est
                                for team in teams.values()
                                if team not in r7_room.teams
                                and team.r9_room is not None])
            scores_out_r9_rooms.append(scores)

    random.shuffle(orders)
    order_scores = []
    best_order = None
    best_score = 10**10
    for order in orders:
        r7_room.set_order(order)
        # Get loss for the order!!!

        # 1. Get collision loss: num of teams in room who get same result
        coll_loss = (4 - len(set(order))) * 5

        # 2. Get out-of-bracket loss
            # For each r8 room the teams in this r7 room end in
            # See how many teams outside that room
            # Fall between the highest and lowest points in that room
        r8_oob_loss = 0
        for r8_room, score_series in zip(team_r8_room, scores_out_r8_rooms):
            if r8_room is None:
                continue
            r8_oob_loss += get_oob_loss(8, r8_room, score_series)
        r9_oob_loss = 0
        for r9_room, score_series in zip(team_r9_room, scores_out_r9_rooms):
            if r9_room is None:
                continue
            r9_oob_loss += get_oob_loss(9, r9_room, score_series)

        # 3. Get pullup loss
        r8_pullup_loss = get_pullup_loss(8, teams, r8_rooms)
        r9_pullup_loss = get_pullup_loss(9, teams, r9_rooms)

        order_score = (coll_loss * 100
                        + (r8_oob_loss + r8_pullup_loss)
                        + (r9_oob_loss + r9_pullup_loss) * 0)
        order_scores.append(order_score)
        if order_score < best_score:
            best_order = order
            best_score = order_score

    for order, order_score in zip(orders, order_scores):
        continue
        print(order, order_score)
    r7_room.set_order(best_order)


def choose_order_for_r8_room(teams, r8_room, r9_rooms):
    """
    Cycle through all possible orders, choose that which has the lowest loss
    """
    # Do infrastructure before loop to save calculations
    team_r9_room = [team.r9_room for team in r8_room.teams
                    if team.r9_room is not None]
    scores_out_r9_rooms = []
    for room in team_r9_room:
        if room is None:
            scores_out_r9_rooms.append(None)
        else:
            scores = pd.Series([team.known + team.r7_est + team.r8_est
                                for team in teams.values()
                                if team not in r8_room.teams
                                and team.r9_room is not None])
            scores_out_r9_rooms.append(scores)

    random.shuffle(orders)
    order_scores = []
    best_order = None
    best_score = 10**10
    best_oob_loss = None
    for order in orders:
        r8_room.set_order(order)

        # 1. Get collision loss: num of teams in room who get same result
        coll_loss = (4 - len(set(order))) * 5

        # 2. Get out-of-bracket loss
            # For each r8 room the teams in this r7 room end in
            # See how many teams outside that room
            # Fall between the highest and lowest points in that room
        oob_loss = 0
        for r9_room, score_series in zip(team_r9_room, scores_out_r9_rooms):
            if r9_room is None:
                continue
            oob_loss += get_oob_loss(9, r9_room, score_series)

        # 3. Get pullup loss
        pullup_loss = get_pullup_loss(9, teams, r9_rooms)

        order_score = coll_loss + oob_loss + pullup_loss
        order_scores.append(order_score)
        if order_score < best_score:
            best_order = order
            best_score = order_score

    r8_room.set_order(best_order)


def import_r7(filename, teams):
    """
    Goes on the output of descent.py
    Uses the r7 sim to figure out what is possible, what is not
    Doesn't really care about the size of a probability, just whether
    it is nonzero
    """
    r7_poss = pd.read_csv(filename, sep="\t", index_col=0)
    for team_name, row in r7_poss.iterrows():
        teams[team_name].r7_poss = [int(i) for i in row[row > 0].index
                                    if i != "count"]


def global_loss(teams, r7_rooms, r8_rooms, r9_rooms):
    """
    Calculate all losses, over round 8 and round 9
    """
    collision_loss = 0
    for room in r7_rooms:
        coll = (4 - len(set([t.r7_est for t in room.teams])))
        collision_loss += coll
    for room in r8_rooms:
        coll = (4 - len(set([t.r8_est for t in room.teams])))
        collision_loss += coll

    oob_loss = 0
    r8_scores = [team.known + team.r7_est for team in teams.values()
                if team.r8_room is not None]
    for room in r8_rooms:
        outside_r8_scores = [i for i in r8_scores]
        for team in room.teams:
            outside_r8_scores.remove(team.known + team.r7_est)
        oob_loss += get_oob_loss(8, room, pd.Series(outside_r8_scores))
    r9_scores = [t.known + t.r7_est + t.r8_est for t in teams.values()
                if t.r9_room is not None]
    for room in r9_rooms:
        outside_r9_scores = [i for i in r9_scores]
        for team in room.teams:
            outside_r9_scores.remove(team.known + team.r7_est + team.r8_est)
        room_oob_loss = get_oob_loss(9, room, pd.Series(outside_r9_scores))
        oob_loss += room_oob_loss

    pullup_loss = (get_pullup_loss(8, teams, r8_rooms)
                    + get_pullup_loss(9, teams, r9_rooms))

    return collision_loss, oob_loss, pullup_loss


def expire_save(teams, loss):
    """
    On expiry, save the current state along with loss
    """
    def map_index_to_value(index):
        if index == "samples": return 0
        if index == "success": return 1 if loss == 0 else 0
        if index == "loss": return loss
        team_name = index[:-3]
        round = int(index[-1])
        if round == 7: return teams[team_name].r7_est
        else: return teams[team_name].r8_est

    try:
        expire_df = pd.read_csv("expire_file.txt", sep="\t", index_col=0)
    except FileNotFoundError:
        expire_df = pd.DataFrame(
            index=[
                f"{t.name}_r{r}"
                for t in teams.values()
                for r in [7, 8]
            ] + ["loss", "samples", "success"]
        )
    cols = [int(i[4:]) for i in expire_df.columns]
    sim_num = 1 if len(cols) == 0 else max(cols) + 1
    new_col = list(expire_df.reset_index()["index"].apply(map_index_to_value))
    expire_df[f"sim_{sim_num}"] = new_col
    open("expire_file.txt", "w").write(expire_df.to_csv(sep="\t"))


def print_zero(teams):
    """
    On the very blessed (and rare) occasion you get to zero loss
    Save to file, just like how round_7_backtab does
    """
    def map_index_to_value(index):
        team_name = index[:-3]
        round = int(index[-1])
        if round == 7: return teams[team_name].r7_est
        else: return teams[team_name].r8_est

    try:
        zero_df = pd.read_csv("zero_file.txt", sep="\t", index_col=0)
    except FileNotFoundError:
        zero_df = pd.DataFrame(
            index=[
                f"{t.name}_r{r}"
                for t in teams.values()
                for r in [7, 8]
            ]
        )
    cols = [int(i[4:]) for i in expire_df.columns]
    sim_num = 1 if len(cols) == 0 else max(cols) + 1
    new_col = list(expire_df.reset_index()["index"].apply(map_index_to_value))
    zero_df[f"sim_{sum_num}"] = new_col
    open("zero_file.txt", "w").write(zero_df.to_csv(sep="\t"))


def run_tests():
    """
    Loops over and over, running the backtabber round after round
    """
    teams, r7_rooms, r8_rooms, r9_rooms = initialise(initialise_directory)
    import_r7(r7_filename, teams)
    i = 0
    while True:
        top = "*" * (13 + len(str(i+1)))
        print(f"{top}\n* FULL RUN {i+1} *\n{top}")
        for j in range(max_search_len):
            print(f"Iteration {j+1}")
            if j < 5:
                for r7_room in r7_rooms:
                    choose_order_for_r7_room(teams, r7_room, r8_rooms)
            random.shuffle(r8_rooms)
            for r8_room in r8_rooms:
                choose_order_for_r8_room(teams, r8_room, r9_rooms)
            loss = global_loss(teams, r7_rooms, r8_rooms, r9_rooms)
            print(f"\t{sum(loss)} ({loss})")
            if sum(loss) == 0:
                print("ZERO")
                print_zero(teams)
                break
            if sum(loss) > cutoff_threshold and j >= cutoff_point - 1:
                print("CUTOFF FAILED")
                break
            if j == max_search_len - 1:
                print("EXPIRED")
                expire_save(teams, sum(loss))

        reset_results(r7_rooms, r8_rooms)
        i += 1




run_tests()
