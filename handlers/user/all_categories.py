import io
from typing import Union

from aiogram import types, Router, F
from aiogram.enums import ParseMode
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.common.common import add_pagination_buttons
from services.buy import BuyService
from services.buyItem import BuyItemService
from services.category import CategoryService
from services.item import ItemService
from services.subcategory import SubcategoryService
from services.user import UserService
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator
from utils.notification_manager import NotificationManager


class AllCategoriesCallback(CallbackData, prefix="all_categories"):
    level: int
    category_id: int
    subcategory_id: int
    price: float
    quantity: int
    total_price: float
    confirmation: bool
    page: int


def create_callback_all_categories(level: int,
                                   category_id: int = -1,
                                   subcategory_id: int = -1,
                                   price: float = 0.0,
                                   total_price: float = 0.0,
                                   quantity: int = 0,
                                   confirmation: bool = False,
                                   page: int = 0):
    return AllCategoriesCallback(level=level, category_id=category_id, subcategory_id=subcategory_id, price=price,
                                 total_price=total_price,
                                 quantity=quantity, confirmation=confirmation, page=page).pack()


all_categories_router = Router()


@all_categories_router.message(F.text == Localizator.get_text_from_key("all_categories"), IsUserExistFilter())
async def all_categories_text_message(message: types.message):
    await all_categories(message)


async def create_category_buttons(page: int):
    categories = await CategoryService.get_unsold(page)
    if categories:
        categories_builder = InlineKeyboardBuilder()
        for category in categories:
            category_button_callback = create_callback_all_categories(level=1, category_id=category.id)
            category_button = types.InlineKeyboardButton(text=category.name, callback_data=category_button_callback)
            categories_builder.add(category_button)
        categories_builder.adjust(2)
        return categories_builder


async def create_subcategory_buttons(category_id: int, page: int = 0):
    current_level = 1
    items = await ItemService.get_unsold_subcategories_by_category(category_id, page)
    subcategories_builder = InlineKeyboardBuilder()
    for item in items:
        subcategory_price = await ItemService.get_price_by_subcategory(item.subcategory_id)
        available_quantity = await ItemService.get_available_quantity(item.subcategory_id)
        subcategory_inline_button = create_callback_all_categories(level=current_level + 1,
                                                                   category_id=category_id,
                                                                   subcategory_id=item.subcategory_id,
                                                                   price=subcategory_price)
        subcategories_builder.add(
            types.InlineKeyboardButton(
                text=Localizator.get_text_from_key("subcategory_button").format(subcategory_name=item.subcategory.name,
                                                                                subcategory_price=subcategory_price,
                                                                                available_quantity=available_quantity),
                callback_data=subcategory_inline_button))
    subcategories_builder.adjust(1)
    return subcategories_builder


async def all_categories(message: Union[Message, CallbackQuery]):
    if isinstance(message, Message):
        category_inline_buttons = await create_category_buttons(0)
        zero_level_callback = create_callback_all_categories(0)
        if category_inline_buttons:
            category_inline_buttons = await add_pagination_buttons(category_inline_buttons, zero_level_callback,
                                                                   CategoryService.get_maximum_page(),
                                                                   AllCategoriesCallback.unpack, None)
            await message.answer(Localizator.get_text_from_key("all_categories"), parse_mode=ParseMode.HTML,
                                 reply_markup=category_inline_buttons.as_markup())
        else:
            await message.answer(Localizator.get_text_from_key("no_categories"), parse_mode=ParseMode.HTML)
    elif isinstance(message, CallbackQuery):
        callback = message
        unpacked_callback = AllCategoriesCallback.unpack(callback.data)
        category_inline_buttons = await create_category_buttons(unpacked_callback.page)
        if category_inline_buttons:
            category_inline_buttons = await add_pagination_buttons(category_inline_buttons, callback.data,
                                                                   CategoryService.get_maximum_page(),
                                                                   AllCategoriesCallback.unpack, None)
            await callback.message.edit_text(Localizator.get_text_from_key("all_categories"), parse_mode=ParseMode.HTML,
                                             reply_markup=category_inline_buttons.as_markup())
        else:
            await callback.message.edit_text(Localizator.get_text_from_key("no_categories"), parse_mode=ParseMode.HTML)


async def show_subcategories_in_category(callback: CallbackQuery):
    unpacked_callback = AllCategoriesCallback.unpack(callback.data)
    subcategory_buttons = await create_subcategory_buttons(unpacked_callback.category_id, page=unpacked_callback.page)
    back_button = types.InlineKeyboardButton(text=Localizator.get_text_from_key("back_to_all_categories"),
                                             callback_data=create_callback_all_categories(
                                                 level=unpacked_callback.level - 1))
    subcategory_buttons = await add_pagination_buttons(subcategory_buttons, callback.data,
                                                       ItemService.get_maximum_page(unpacked_callback.category_id),
                                                       AllCategoriesCallback.unpack,
                                                       back_button)
    await callback.message.edit_text(Localizator.get_text_from_key("admin_delete_subcategory_msg"),
                                     reply_markup=subcategory_buttons.as_markup(),
                                     parse_mode=ParseMode.HTML)


async def select_quantity(callback: CallbackQuery):
    unpacked_callback = AllCategoriesCallback.unpack(callback.data)
    price = unpacked_callback.price
    subcategory_id = unpacked_callback.subcategory_id
    category_id = unpacked_callback.category_id
    current_level = unpacked_callback.level
    
    description = await ItemService.get_description(subcategory_id)
    
    count_builder = InlineKeyboardBuilder()
    quantities = list(range(1, 11)) + [20, 50, 100]
    
    for quantity in quantities:
        total_price = price * quantity
        count_button_callback = create_callback_all_categories(
            level=current_level + 1,
            category_id=category_id,
            subcategory_id=subcategory_id,
            price=price,
            quantity=quantity,
            total_price=total_price
        )
        count_button_inline = types.InlineKeyboardButton(
            text=str(quantity),
            callback_data=count_button_callback
        )
        count_builder.add(count_button_inline)

    back_button = types.InlineKeyboardButton(text=Localizator.get_text_from_key("admin_back_button"),
                                             callback_data=create_callback_all_categories(level=current_level - 1,
                                                                                          category_id=category_id))
    count_builder.add(back_button)
    count_builder.adjust(3)
    subcategory = await SubcategoryService.get_by_primary_key(subcategory_id)
    await callback.message.edit_text(
        text=Localizator.get_text_from_key("select_quantity").format(subcategory_name=subcategory.name,
                                                                     price=price,
                                                                     description=description),
        reply_markup=count_builder.as_markup(),
        parse_mode=ParseMode.HTML)


async def buy_confirmation(callback: CallbackQuery):
    unpacked_callback = AllCategoriesCallback.unpack(callback.data)
    price = unpacked_callback.price
    total_price = unpacked_callback.total_price
    subcategory_id = unpacked_callback.subcategory_id
    category_id = unpacked_callback.category_id
    current_level = unpacked_callback.level
    quantity = unpacked_callback.quantity
    description = await ItemService.get_description(subcategory_id)
    confirmation_builder = InlineKeyboardBuilder()
    confirm_button_callback = create_callback_all_categories(level=current_level + 1,
                                                             category_id=category_id,
                                                             subcategory_id=subcategory_id,
                                                             price=price,
                                                             total_price=total_price,
                                                             quantity=quantity,
                                                             confirmation=True)
    decline_button_callback = create_callback_all_categories(level=current_level + 1,
                                                             category_id=category_id,
                                                             subcategory_id=subcategory_id,
                                                             price=price,
                                                             total_price=total_price,
                                                             quantity=quantity,
                                                             confirmation=False)
    confirmation_button = types.InlineKeyboardButton(text=Localizator.get_text_from_key("admin_confirm"),
                                                     callback_data=confirm_button_callback)
    decline_button = types.InlineKeyboardButton(text=Localizator.get_text_from_key("admin_decline"),
                                                callback_data=decline_button_callback)
    back_button = types.InlineKeyboardButton(text=Localizator.get_text_from_key("admin_back_button"),
                                             callback_data=create_callback_all_categories(level=current_level - 1,
                                                                                          category_id=category_id,
                                                                                          subcategory_id=subcategory_id,
                                                                                          price=price))
    confirmation_builder.add(confirmation_button, decline_button, back_button)
    confirmation_builder.adjust(2)
    subcategory = await SubcategoryService.get_by_primary_key(subcategory_id)
    await callback.message.edit_text(
        text=Localizator.get_text_from_key("buy_confirmation").format(subcategory_name=subcategory.name,
                                                                      price=price,
                                                                      description=description,
                                                                      quantity=quantity,
                                                                      total_price=total_price),
        reply_markup=confirmation_builder.as_markup(),
        parse_mode=ParseMode.HTML)


async def buy_processing(callback: CallbackQuery):
    unpacked_callback = AllCategoriesCallback.unpack(callback.data)
    confirmation = unpacked_callback.confirmation
    total_price = unpacked_callback.total_price
    subcategory_id = unpacked_callback.subcategory_id
    quantity = unpacked_callback.quantity
    telegram_id = callback.from_user.id
    is_in_stock = await ItemService.get_available_quantity(subcategory_id) >= quantity
    is_enough_money = await UserService.is_buy_possible(telegram_id, total_price)
    back_to_main_builder = InlineKeyboardBuilder()
    back_to_main_callback = create_callback_all_categories(level=0)
    back_to_main_button = types.InlineKeyboardButton(text=Localizator.get_text_from_key("all_categories"),
                                                     callback_data=back_to_main_callback)
    back_to_main_builder.add(back_to_main_button)
    if confirmation and is_in_stock and is_enough_money:
        await UserService.update_consume_records(telegram_id, total_price)
        sold_items = await ItemService.get_bought_items(subcategory_id, quantity)
        user = await UserService.get_by_tgid(telegram_id)
        new_buy_id = await BuyService.insert_new(user, quantity, total_price)
        await BuyItemService.insert_many(sold_items, new_buy_id)
        await ItemService.set_items_sold(sold_items)
        if quantity > 1:
            subcategory = await SubcategoryService.get_by_primary_key(subcategory_id)
            filename = f"{user.id}-{new_buy_id}-{subcategory.name}-{quantity}-{total_price}.txt"
            message = await create_message_with_bought_items(sold_items)
            file_content = message.encode('utf-8')
            file = BufferedInputFile(file_content, filename=filename)
            await callback.message.answer_document(
                document=file,
                caption=Localizator.get_text_from_key("purchase_successful"),
                parse_mode=ParseMode.HTML
            )
            await callback.message.delete()
        else:
            message = await create_message_with_bought_items(sold_items)
            await callback.message.edit_text(text=message, parse_mode=ParseMode.HTML)
        
        await NotificationManager.new_buy(subcategory_id, quantity, total_price, user)
    elif confirmation is False:
        await callback.message.edit_text(text=Localizator.get_text_from_key("admin_declined"),
                                         parse_mode=ParseMode.HTML,
                                         reply_markup=back_to_main_builder.as_markup())
    elif is_enough_money is False:
        await callback.message.edit_text(text=Localizator.get_text_from_key("insufficient_funds"),
                                         parse_mode=ParseMode.HTML,
                                         reply_markup=back_to_main_builder.as_markup())
    elif is_in_stock is False:
        await callback.message.edit_text(text=Localizator.get_text_from_key("out_of_stock"),
                                         parse_mode=ParseMode.HTML,
                                         reply_markup=back_to_main_builder.as_markup())

async def create_message_with_bought_items(bought_data: list):
    message = ""
    for count, item in enumerate(bought_data, start=1):
        private_data = item.private_data
        message += Localizator.get_text_from_key("purchased_item").format(count=count, private_data=private_data)
    return message


@all_categories_router.callback_query(AllCategoriesCallback.filter(), IsUserExistFilter())
async def navigate_categories(call: CallbackQuery, callback_data: AllCategoriesCallback):
    current_level = callback_data.level

    levels = {
        0: all_categories,
        1: show_subcategories_in_category,
        2: select_quantity,
        3: buy_confirmation,
        4: buy_processing
    }

    current_level_function = levels[current_level]

    await current_level_function(call)
