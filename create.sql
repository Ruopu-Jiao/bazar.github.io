
-- Define Schemas for Database
CREATE TABLE Buyers
(userID INTEGER NOT NULL PRIMARY KEY,
email VARCHAR(256) NOT NULL,
password VARCHAR(256) NOT NULL,
currentBalance DECIMAL(10,2) NOT NULL,
first_name VARCHAR(256) NOT NULL,
last_name VARCHAR(256) NOT NULL,
image VARCHAR(256)); -- Store file path here; file names are unique and are dependent on the userID
		     -- Set to random default avatar if none input in registration

CREATE TABLE Sellers
(userID INTEGER NOT NULL PRIMARY KEY REFERENCES Buyers(userID),
organization VARCHAR(256) NOT NULL, -- Organization/Store name displayed;
				    -- Default set to user's name if none input;
				    -- the user can set it to their own name, 
				    -- but this is the name displayed on the seller page
image VARCHAR(256), -- Optional, image for organization not for personal user profile
description VARCHAR(1250), -- Optional
avg_rating DECIMAL(10,2) NOT NULL,
CHECK (avg_rating>=0));

CREATE TABLE Items
(itemID INTEGER NOT NULL PRIMARY KEY,
sellerID INTEGER NOT NULL REFERENCES Sellers(userID),
name VARCHAR(256) NOT NULL,
price DECIMAL(10,2) NOT NULL,
avg_rating DECIMAL(10,2) NOT NULL,
num INTEGER NOT NULL, -- Number of items available
description VARCHAR(1250), -- Optional
image VARCHAR(256) -- Optional
);
-- CHECK (items.num>=0 AND items.avg_rating>=0 AND items.price>=0));

CREATE TABLE Category
(name VARCHAR(256) NOT NULL PRIMARY KEY,
topItemOne INTEGER REFERENCES Items(itemID), -- item ID for most popular item in category 
					     -- (NULL only if no items in category)
topItemTwo INTEGER REFERENCES Items(itemID), -- item ID for 2nd most popular in category
topItemThree INTEGER REFERENCES Items(itemID) -- item ID for 3rd most popular in category
);					-- if all 3 items null: show 3 alphabetically first items

CREATE TABLE ItemInCategory
(itemID INTEGER NOT NULL REFERENCES Items(itemID),
category VARCHAR(256) NOT NULL REFERENCES Category(name),
PRIMARY KEY(itemID, category)
);

CREATE TABLE Cart
(buyerID INTEGER NOT NULL REFERENCES Buyers(userID),
itemID INTEGER NOT NULL REFERENCES Items(itemID),
num INTEGER NOT NULL, -- Quantity in cart
PRIMARY KEY(buyerID, itemID),
CHECK (num>=0)
);

CREATE TABLE Purchase
(buyerID INTEGER NOT NULL REFERENCES Buyers(userID),
itemID INTEGER NOT NULL REFERENCES Items(itemID),
dayTime TIMESTAMP NOT NULL, -- Date, Time, Timezone data
num INTEGER NOT NULL, -- Quantity purchased
PRIMARY KEY(buyerID, itemID, dayTime),
CHECK (num >=0)
);

CREATE TABLE ItemReview
(buyerID INTEGER NOT NULL REFERENCES Buyers(userID), -- Field set by website
itemID INTEGER NOT NULL REFERENCES Items(itemID), -- Field set by website
numStars INTEGER NOT NULL, -- Field for User to input
comments VARCHAR(1250), -- Optional, field for User to input
dayTime TIMESTAMP NOT NULL, -- Field set by website (current time of submission)
PRIMARY KEY(buyerID, itemID),
CHECK (numStars>=0)
);

CREATE TABLE SellerReview
(buyerID INTEGER NOT NULL REFERENCES Buyers(userID), -- Field set by website
sellerID INTEGER NOT NULL REFERENCES Sellers(userID), -- Field set by website
numStars INTEGER NOT NULL, -- Field for User to input
comments VARCHAR(1250), -- Optional, field for User to input
dayTime TIMESTAMP NOT NULL, -- Field set by website (current time of submission)
PRIMARY KEY(buyerID, sellerID),
CHECK (numStars>=0)
);


-- SQL VIEWs for more complex database accesses
-- Combine purchase and items
CREATE VIEW itemhistory AS
SELECT purchase.buyerID, purchase.itemID, items.name, items.price, purchase.num, purchase.dayTime, items.sellerID
FROM purchase
INNER JOIN items
ON purchase.itemID = items.itemID;

CREATE VIEW iteminformation AS
SELECT Items.itemID, Items.name, Items.price, Items.avg_rating, Items.description, Items.image, ItemInCategory.category, Sellers.organization
FROM Items, ItemInCategory, Sellers
WHERE Items.itemID = ItemInCategory.itemID AND Items.sellerID = Sellers.userID;

CREATE VIEW itemPurchases AS
SELECT itemhistory.buyerID, itemhistory.itemID, itemhistory.name, itemhistory.price, itemhistory.num, itemhistory.dayTime, sellers.organization, itemhistory.sellerID
FROM itemhistory
INNER JOIN sellers
ON itemhistory.sellerID = sellers.userID;

-- Combine cart and items
CREATE VIEW cartitems AS
SELECT cart.buyerID, items.itemID, items.name, items.sellerID, items.price, cart.num
FROM cart
INNER JOIN items
ON cart.itemID = items.itemID;

-- Combine cart, items, seller
CREATE VIEW cartitem_seller AS
SELECT cartitems.buyerID, cartitems.itemID, cartitems.name, sellers.organization, cartitems.price, cartitems.num, cartitems.sellerID
FROM cartitems
INNER JOIN sellers
ON cartitems.sellerID = sellers.userID;

-- Combine seller and items
CREATE VIEW itemstoseller AS
SELECT sellers.userID, items.itemID, items.name, items.price
FROM sellers
INNER JOIN items
ON sellers.userID = items.sellerID;

-- combine with purchase
CREATE VIEW itemsellerpurchase AS
SELECT itemstoseller.userID, itemstoseller.itemID, itemstoseller.name, itemstoseller.price, purchase.buyerID, purchase.num, purchase.daytime
FROM itemstoseller
INNER JOIN purchase
ON itemstoseller.itemID = purchase.itemID;

-- combine with item review
CREATE VIEW viewitemreviews AS
SELECT itemsellerpurchase.userID, itemsellerpurchase.itemID, itemsellerpurchase.name, itemsellerpurchase.price, itemsellerpurchase.buyerID, itemsellerpurchase.num, itemsellerpurchase.daytime, itemreview.numstars, itemreview.comments
FROM itemsellerpurchase
INNER JOIN itemreview
ON itemsellerpurchase.itemID = itemreview.itemID AND itemsellerpurchase.buyerID = itemreview.buyerID;

-- combine with seller review
CREATE VIEW transactionhistory AS
SELECT viewitemreviews.userID, viewitemreviews.itemID, viewitemreviews.name, viewitemreviews.price, viewitemreviews.buyerID, viewitemreviews.num, viewitemreviews.numstars, viewitemreviews.comments, viewitemreviews.daytime, sellerreview.numstars AS seller_rating, sellerreview.comments AS seller_comments
FROM viewitemreviews
INNER JOIN sellerreview
ON viewitemreviews.userID = sellerreview.sellerID AND viewitemreviews.buyerID = sellerreview.buyerID;

-- combine with buyers
CREATE VIEW final AS
SELECT  transactionhistory.userID,  transactionhistory.itemID, transactionhistory.name,  transactionhistory.price,  transactionhistory.buyerID,  transactionhistory.num,  transactionhistory.numstars,  transactionhistory.comments,  transactionhistory.daytime,  transactionhistory.seller_rating,  transactionhistory.seller_comments, buyers.first_name, buyers.last_name
FROM transactionhistory
INNER JOIN buyers
ON transactionhistory.buyerID = buyers.userID;


-- Triggers to Ensure Data Clarity

delimiter //
CREATE TRIGGER no_itempurchase_no_review BEFORE INSERT OR UPDATE ON ItemReview
       FOR EACH ROW
       BEGIN
	DECLARE msg varchar(128);
	IF NOT EXISTS(SELECT *
		      FROM Purchase
		      WHERE NEW.buyerID = Purchase.buyerID
			AND NEW.itemID = Purchase.itemID)
		-- THEN RAISE EXCEPTION 'Cannot review an item you have never purchased.';
	THEN
		SET msg = concat('Error: Cannot review an item you have never purchased.';
       		signal sqlstate '45000' set message_text = msg;
	END IF;
       END;
//
delimiter;


delimiter //
CREATE TRIGGER no_sellerpurchase_no_review BEFORE INSERT OR UPDATE ON SellerReview
       FOR EACH ROW
       BEGIN
	DECLARE msg varchar(128);
	IF NOT EXISTS(SELECT *
		      FROM Purchase, Items
		      WHERE NEW.buyerID = Purchase.buyerID
			AND PURCHASE.itemID = Items.ID
			AND Items.sellerID = NEW.sellerID)
	THEN
		SET msg = concat('Error: Cannot review a seller from whom you have never purchased an item.';
       		signal sqlstate '45000' set message_text = msg;
	END IF;
       END;
//
delimiter;


delimiter //
CREATE TRIGGER updAveSellerRatings AFTER INSERT OR UPDATE ON SellerReview
       FOR EACH ROW
       BEGIN

	WITH X AS (SELECT sellerID, AVG(numStars) AS avgR
                   FROM SellerReview, Sellers
                   WHERE Sellers.sellerID = SellerReview.sellerID
                   GROUP BY sellerID)
	UPDATE Sellers SET avg_rating = X.avgR
	WHERE X.sellerID = NEW.sellerID
	  AND NEW.sellerID = Sellers.sellerID;

       END;
//
delimiter;


delimiter //
CREATE TRIGGER updAveItemRatings AFTER INSERT OR UPDATE ON ItemReview
       FOR EACH ROW
       BEGIN
	WITH X AS (SELECT itemID, AVG(numStars) AS avgR
                        FROM ItemReview, Items
                        WHERE Items.itemID = ItemReview.itemID
                        GROUP BY itemID)
		UPDATE Items SET avg_rating = X.avgR
		WHERE X.itemID = NEW.itemID;

	-- Updating Top Item in Category
	WITH Y AS (SELECT Items.itemID AS item, Category.name AS category, Items.avg_rating AS top
		   FROM ItemInCategory, Items, Category
		   WHERE Items.itemID = ItemInCategory.itemID
		     AND ItemInCategory.category = Category.name
		     AND (Category.name, Items.avg_rating) IN (
			SELECT Category.name, max(Items.avg_rating)
			FROM Category, Items
			WHERE Items.itemID = ItemInCategory.itemID
			  AND ItemInCategory.category = Category.name
			GROUP BY Category.name
			)
		   )
	UPDATE Category SET topItemOne = Y.item
	WHERE Y.category = Category.name;

	-- Updating Second Top-Rated Item in Category
	WITH Z AS (SELECT Items.itemID AS item, Category.name AS category, Items.avg_rating AS second
		   FROM ItemInCategory, Items, Category
		   WHERE Items.itemID = ItemInCategory.itemID
		     AND ItemInCategory.category = Category.name
		     AND (Category.name, Items.avg_rating) IN (
			SELECT Category.name, max(Items.avg_rating)
			FROM Category, Items, Y
			WHERE Items.itemID = ItemInCategory.itemID
			  AND ItemInCategory.category = Category.name
			  AND Y.category = Category.name
			  AND Items.avg_rating <= Y.top
			  AND Items.itemID <> Category.topItemOne
			GROUP BY Category.name
			)
		   )
	UPDATE Category SET topItemTwo = Z.item
	WHERE Z.category = Category.name;

	-- Updating Third Top-Rated Item in Category
	WITH L AS (SELECT Items.itemID AS item, Category.name AS category, Items.avg_rating AS third
		   FROM ItemInCategory, Items, Category
		   WHERE Items.itemID = ItemInCategory.itemID
		     AND ItemInCategory.category = Category.name
		     AND (Category.name, Items.avg_rating) IN (
			SELECT Category.name, max(Items.avg_rating)
			FROM Category, Items, Z
			WHERE Items.itemID = ItemInCategory.itemID
			  AND ItemInCategory.category = Category.name
			  AND Z.category = Category.name
			  AND Items.avg_rating <= Z.second
			  AND Items.itemID <> (Category.topItemOne OR Category.topItemTwo)
			GROUP BY Category.name
			)
		   )
	UPDATE Category SET topItemThree = L.item
	WHERE L.category = Category.name;

       END;
//
delimiter;



